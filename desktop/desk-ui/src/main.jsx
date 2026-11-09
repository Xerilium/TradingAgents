import React from 'react';
import {createRoot} from 'react-dom/client';
import {CssBaseline, SvgIcon, ThemeProvider, createTheme} from '@mui/material';
import {DeskProvider} from './DeskContext.jsx';
import App from './App.jsx';

const theme = createTheme({
  palette: {mode: 'dark', primary: {main: '#79ce9e', contrastText: '#10271b'},
    background: {default: '#111920', paper: '#1b252f'}, divider: '#34414d',
    text: {primary: '#e1e8ee', secondary: '#a5b3c0'}, success: {main: '#7bd5a2'},
    warning: {main: '#e6c17d'}, error: {main: '#f29199'}},
  shape: {borderRadius: 3},
  typography: {fontFamily: '"Segoe UI Variable Text","Segoe UI",Arial,sans-serif', fontSize: 14,
    h1: {fontSize: 26, fontWeight: 600}, h2: {fontSize: 22, fontWeight: 600},
    h3: {fontSize: 18, fontWeight: 600}, button: {textTransform: 'none'}},
  components: {
    MuiButton: {defaultProps: {variant: 'outlined'}, styleOverrides: {root: {minHeight: 36}}},
    MuiTextField: {defaultProps: {size: 'small', variant: 'outlined'}},
    MuiTableCell: {styleOverrides: {root: {fontVariantNumeric: 'tabular-nums', verticalAlign: 'top'}, head: {fontWeight: 600}}},
    MuiAccordion: {defaultProps: {disableGutters: true}},
    MuiAccordionSummary: {defaultProps: {expandIcon: <SvgIcon fontSize="small"><path d="M7 10l5 5 5-5z"/></SvgIcon>}},
    MuiCssBaseline: {styleOverrides: {
      'html,body,#root': {height: '100%', margin: 0},
      ':root': {'--paper': '#1b252f', '--ink': '#e1e8ee', '--line': '#34414d',
        '--positive': '#7bd5a2', '--negative': '#f29199',
        '--font': '"Segoe UI Variable Text","Segoe UI",Arial,sans-serif', '--text-data': '14px'},
      'body': {overflow: 'hidden'},
      ':focus-visible': {outline: '2px solid #86d6ab', outlineOffset: 2},
      '@media (prefers-reduced-motion: reduce)': {'*,*::before,*::after': {animationDuration: '0.01ms !important', transitionDuration: '0.01ms !important'}},
    }},
  },
});

createRoot(document.getElementById('root')).render(
  <ThemeProvider theme={theme}><CssBaseline/><DeskProvider><App/></DeskProvider></ThemeProvider>,
);
