import React, {useState} from 'react';
import {Accordion, AccordionDetails, AccordionSummary, Box, Checkbox, Chip, Paper, Stack,
  Table, TableBody, TableCell, TableContainer, TableHead, TablePagination, TableRow, Typography} from '@mui/material';

export const number = value => value === null || value === undefined || typeof value === 'boolean' ||
  typeof value === 'string' && !value.trim() || !Number.isFinite(Number(value)) ? null : Number(value);
export const money = value => number(value) === null ? 'Unavailable' :
  new Intl.NumberFormat('en-US', {style: 'currency', currency: 'USD'}).format(Number(value));
export const dateTime = value => !value || !Number.isFinite(Date.parse(value)) ? 'Unavailable' :
  new Intl.DateTimeFormat('en-US', {dateStyle: 'medium', timeStyle: 'medium', timeZone: 'America/Los_Angeles'}).format(new Date(value));

export function Page({title, subtitle, actions, children}) {
  return <Stack spacing={2} sx={{p: 2, minWidth: 0}}>
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

export function DataTable({rows = [], columns, getRowId = row => row.id ?? row.symbol ?? row.name,
  onRowClick, selectedIds, onSelectionChange, empty = 'No records available.'}) {
  const [page, setPage] = useState(0), [size, setSize] = useState(25);
  const currentPage = Math.min(page, Math.max(0, Math.ceil(rows.length / size) - 1));
  const selected = selectedIds instanceof Set ? selectedIds : new Set(selectedIds || []);
  const toggle = id => {
    const next = new Set(selected);
    if (next.has(id)) next.delete(id); else next.add(id);
    onSelectionChange?.(next);
  };
  return <Paper variant="outlined" sx={{minWidth: 0}}>
    <TableContainer>
      <Table size="small">
        <TableHead><TableRow>{onSelectionChange && <TableCell padding="checkbox"/>}
          {columns.map(column => <TableCell key={column.id} align={column.numeric ? 'right' : 'left'}>{column.label}</TableCell>)}
        </TableRow></TableHead>
        <TableBody>{rows.length ? rows.slice(currentPage * size, (currentPage + 1) * size).map(row => {
          const id = getRowId(row);
          if (id === undefined || id === null) throw new Error('Table records require stable source identities.');
          return <TableRow key={id} hover={Boolean(onRowClick)} selected={selected.has(id)}
            tabIndex={onRowClick ? 0 : undefined}
            onClick={onRowClick ? () => onRowClick(row) : undefined}
            onKeyDown={onRowClick ? event => {
              if (event.target === event.currentTarget && ['Enter', ' '].includes(event.key)) {
                event.preventDefault(); onRowClick(row);
              }
            } : undefined} sx={onRowClick ? {cursor: 'pointer'} : undefined}>
            {onSelectionChange && <TableCell padding="checkbox"><Checkbox checked={selected.has(id)}
              slotProps={{input: {'aria-label': `Select ${id}`}}}
              onClick={event => event.stopPropagation()} onChange={() => toggle(id)}/></TableCell>}
            {columns.map(column => <TableCell key={column.id} align={column.numeric ? 'right' : 'left'}>
              {column.render ? column.render(row) : String(row[column.id] ?? 'Unavailable')}
            </TableCell>)}
          </TableRow>;
        }) : <TableRow><TableCell colSpan={columns.length + Number(Boolean(onSelectionChange))}>{empty}</TableCell></TableRow>}</TableBody>
      </Table>
    </TableContainer>
    <TablePagination component="div" count={rows.length} page={currentPage} rowsPerPage={size} rowsPerPageOptions={[25, 50, 100]}
      onPageChange={(_, next) => setPage(next)} onRowsPerPageChange={event => {setSize(Number(event.target.value)); setPage(0);}}/>
  </Paper>;
}
