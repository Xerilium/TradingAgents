import React, {useMemo, useRef} from 'react';
import {Accordion, AccordionDetails, AccordionSummary, Box, Chip, Stack, Typography} from '@mui/material';
import {DataGrid} from '@mui/x-data-grid';

export const number = value => !['number', 'string'].includes(typeof value) ||
  typeof value === 'string' && !value.trim() || !Number.isFinite(Number(value)) ? null : Number(value);
export const money = value => number(value) === null ? 'Unavailable' :
  new Intl.NumberFormat('en-US', {style: 'currency', currency: 'USD'}).format(Number(value));
export const dateTime = value => !value || !Number.isFinite(Date.parse(value)) ? 'Unavailable' :
  new Intl.DateTimeFormat('en-US', {dateStyle: 'medium', timeStyle: 'medium', timeZone: 'America/Los_Angeles'}).format(new Date(value));

export function Page({title, subtitle, actions, children, tabbed = false}) {
  return <Stack spacing={2} sx={{p: 2, minWidth: 0, ...(tabbed && {height: '100%', minHeight: 0, overflow: 'hidden',
    '& > :not([role="tabpanel"])': {flexShrink: 0},
    '& > [role="tabpanel"]': {flex: 1, minHeight: 0, overflow: 'auto'}})}}>
    <Stack direction="row" spacing={2}   useFlexGap  sx={{alignItems: "center", justifyContent: "space-between", flexWrap: "wrap"}}>
      <Box><Typography variant="h1">{title}</Typography>{subtitle && <Typography color="text.secondary">{subtitle}</Typography>}</Box>
      {actions && <Stack direction="row" spacing={1} useFlexGap  sx={{flexWrap: "wrap"}}>{actions}</Stack>}
    </Stack>
    {children}
  </Stack>;
}

export function Evidence({title = 'Source details', data}) {
  return <Accordion disableGutters elevation={0} sx={{border: 1, borderColor: 'divider'}}>
    <AccordionSummary aria-label={title}><Typography>{title}</Typography></AccordionSummary>
    <AccordionDetails><Box component="pre" sx={{m: 0, whiteSpace: 'pre-wrap', overflowWrap: 'anywhere',
      fontFamily: 'monospace', fontSize: 13}}>{JSON.stringify(data ?? null, null, 2)}</Box></AccordionDetails>
  </Accordion>;
}

export function Status({value}) {
  const label = String(value ?? 'Unavailable');
  const color = /^(filled|completed|reconciled|accepted|ready|connected|passed|enabled)$/i.test(label) ? 'success' :
    /^(failed|rejected|error|outcome_unknown|unresolved)$/i.test(label) ? 'error' :
    /^(blocked|expired|incomplete|stale|paused|review_required)$/i.test(label) ? 'warning' : 'default';
  return <Chip size="small" variant="outlined" color={color} label={label.replaceAll('_', ' ')}/>;
}

export function nativeReportColumns(report) {
  const cell = value => value == null ? 'Unavailable' : typeof value === 'object' ? JSON.stringify(value) : String(value);
  return [{id: 'index', label: (report.index_names || []).map(name => name || 'Index').join(' / ') || 'Index',
    type: report.index?.some(value => value?.iso) ? 'dateTime' : 'string',
    value: row => row.index?.iso ?? row.index, render: row => cell(row.index)},
  ...report.columns.map((name, i) => {
    const dated = report.data.some(row => row[i]?.iso);
    const numeric = !dated && /quantity|qty|price|avg_px|last_px|pnl|balance|^total$|^free$|^locked$|commission|amount|notional|^ts_/.test(name);
    return {id: name, label: name, type: dated ? 'dateTime' : undefined,
      numeric, value: row => {
        const value = row.cells[i]?.iso ?? row.cells[i];
        const money = numeric && typeof value === 'string' && value.match(/^([-+]?(?:\d+|\d{1,3}(?:[,_]\d{3})+)(?:\.\d+)?) [A-Z]{3}$/);
        return money ? money[1].replace(/[,_]/g, '') : value;
      }, render: row => cell(row.cells[i])};
  })];
}

const automaticRowHeight = () => 'auto';

export function DataTable({rows = [], columns, getRowId = row => row.id ?? row.symbol ?? row.name,
  onRowClick, selectedIds, onSelectionChange, empty = 'No records available.', label = 'Data records', ...gridProps}) {
  const latest = useRef(null);
  latest.current = Object.fromEntries(columns.map(column => [column.id, column]));
  const gridRows = useMemo(() => rows.map(source => {
    const id = getRowId(source);
    if (typeof id !== 'string' && typeof id !== 'number') throw new Error('Grid records require stable source identities.');
    return {id, source};
  }), [rows, getRowId]);
  const selectionModel = useMemo(() => selectedIds === undefined ? undefined : {type: 'include', ids: new Set(selectedIds)}, [selectedIds]);
  // Keep the grid's column identity, widths and order while renderers read the latest bound records and drafts.
  const shape = JSON.stringify(columns.map(c => [c.id, c.label, c.numeric, c.type, c.sortable, c.filterable, c.minWidth]));
  const gridColumns = useMemo(() => columns.map(column => {
    const type = column.type || (column.numeric ? 'number' : 'string');
    const raw = row => {
      const current = latest.current[column.id] ?? column;
      return current.value ? current.value(row.source) : row.source?.[column.id];
    };
    return {field: column.id, headerName: column.label, type, flex: 1, minWidth: column.minWidth || 160,
      sortable: column.sortable ?? Boolean(column.label), filterable: column.filterable ?? Boolean(column.label),
      disableExport: !column.label,
      valueGetter: (_, row) => {
        const value = raw(row);
        if (type === 'number') return number(value);
        if (type === 'date' || type === 'dateTime') return value && Number.isFinite(Date.parse(value)) ? new Date(value) : null;
        if (type === 'boolean') return typeof value === 'boolean' ? value : null;
        return value === null || value === undefined ? null : typeof value === 'object' ? JSON.stringify(value) : String(value);
      },
      valueFormatter: (_, row) => {
        const value = raw(row);
        return value === null || value === undefined || value === '' ? 'Unavailable' : typeof value === 'object' ? JSON.stringify(value) : String(value);
      },
      renderCell: params => {
        const current = latest.current[column.id] ?? column;
        return current.render ? current.render(params.row.source) : params.formattedValue;
      }};
  }), [shape]);
  const activate = (params, event) => {
    if (params.field === '__check__' || event.target.closest?.('button,a,input,select,textarea,[role="button"],[role="checkbox"],[contenteditable="true"]')) return;
    onRowClick?.(params.row.source);
  };
  // Grid search and editing must not submit an enclosing settings form.
  return <Box onKeyDown={event => {if (event.key === 'Enter' && event.target.closest?.('input')) event.preventDefault();}}
    sx={{height: rows.length ? 'min(520px, 65vh)' : 240, minHeight: 220, minWidth: 0, width: '100%'}}>
    <DataGrid rows={gridRows} columns={gridColumns} label={label} showToolbar
      density="compact" getRowHeight={automaticRowHeight} disableRowSelectionOnClick
      checkboxSelection={Boolean(onSelectionChange)} disableRowSelectionExcludeModel keepNonExistentRowsSelected
      {...(selectionModel ? {rowSelectionModel: selectionModel} : {})}
      onRowSelectionModelChange={onSelectionChange ? model => onSelectionChange(new Set(model.ids)) : undefined}
      onRowClick={onRowClick ? activate : undefined}
      onCellKeyDown={onRowClick ? (params, event) => {if (event.key === 'Enter') activate(params, event);} : undefined}
      initialState={{pagination: {paginationModel: {page: 0, pageSize: 25}}}} pageSizeOptions={[25, 50, 100]}
      localeText={{noRowsLabel: empty, noResultsOverlayLabel: 'No records match the grid filters.'}}
      slotProps={{toolbar: {printOptions: {disableToolbarButton: true}, csvOptions: {disableToolbarButton: true}}}}
      sx={{'& .MuiDataGrid-cell': {py: 1, whiteSpace: 'normal', overflowWrap: 'anywhere'},
        '& .MuiDataGrid-cell > .MuiStack-root': {flexWrap: 'wrap', gap: 1}}}
      {...gridProps}/>
  </Box>;
}
