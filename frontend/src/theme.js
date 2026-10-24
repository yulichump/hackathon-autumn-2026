
import { createTheme } from '@mui/material/styles';

const theme = createTheme({
  palette: {
    mode: 'dark',

    primary: {
      main: '#16B9CF',
      light: '#55D3E3',
      dark: '#0D91A4',
      contrastText: '#172226',
    },

    secondary: {
      main: '#A7B0BE',
    },

    background: {
      default: '#202226',
      paper: '#2D2D2D',
    },

    text: {
      primary: '#F4F7FA',
      secondary: '#A7ADB7',
    },

    divider: '#41454C',

    success: {
      main: '#42D6A4',
    },

    error: {
      main: '#FF727C',
    },

    warning: {
      main: '#F4BD62',
    },

    info: {
      main: '#65BFFF',
    },
  },

  shape: {
    borderRadius: 12,
  },

  typography: {
    fontFamily: 'Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',

    h4: {
      fontWeight: 700,
      letterSpacing: '-0.035em',
    },

    h5: {
      fontWeight: 650,
      letterSpacing: '-0.025em',
    },

    h6: {
      fontWeight: 600,
    },

    button: {
      textTransform: 'none',
      fontWeight: 600,
      letterSpacing: 0,
    },
  },

  components: {
    MuiCssBaseline: {
      styleOverrides: {
        '*': {
          boxSizing: 'border-box',
        },

        body: {
          minWidth: 320,
          backgroundColor: '#202226',
        },

        '::selection': {
          backgroundColor: '#16B9CF',
          color: '#172226',
        },

        '*::-webkit-scrollbar': {
          width: 8,
          height: 8,
        },

        '*::-webkit-scrollbar-track': {
          background: '#202226',
        },

        '*::-webkit-scrollbar-thumb': {
          background: '#50555E',
          borderRadius: 8,
        },
      },
    },

    MuiButton: {
      styleOverrides: {
        root: {
          borderRadius: 9,
          padding: '8px 16px',
          transition: 'background-color 0.2s ease, transform 0.2s ease',
        },

        containedPrimary: {
          color: '#172226',
          boxShadow: 'none',

          '&:hover': {
            backgroundColor: '#55D3E3',
            boxShadow: '0 4px 18px rgba(22, 185, 207, 0.16)',
            transform: 'translateY(-1px)',
          },
        },

        outlined: {
          borderColor: '#50555E',

          '&:hover': {
            borderColor: '#16B9CF',
            backgroundColor: 'rgba(22, 185, 207, 0.06)',
          },
        },
      },
    },

    MuiCard: {
      styleOverrides: {
        root: {
          backgroundImage: 'none',
          backgroundColor: '#2D2D2D',
          border: '1px solid #41454C',
          borderRadius: 16,
          boxShadow: '0 6px 24px rgba(0, 0, 0, 0.10)',
        },
      },
    },

    MuiPaper: {
      styleOverrides: {
        root: {
          backgroundImage: 'none',
          backgroundColor: '#2D2D2D',
        },
        rounded: {
          borderRadius: 14,
        },
      },
    },

    MuiTableContainer: {
      styleOverrides: {
        root: {
          border: '1px solid #41454C',
          borderRadius: 14,
          overflowX: 'auto',
          backgroundColor: '#2D2D2D',
        },
      },
    },

    MuiTableCell: {
      styleOverrides: {
        root: {
          borderBottom: '1px solid #41454C',
          padding: '14px 16px',
          whiteSpace: 'nowrap',
        },

        head: {
          color: '#A7ADB7',
          backgroundColor: '#26282D',
          fontSize: '0.75rem',
          fontWeight: 700,
          textTransform: 'uppercase',
          letterSpacing: '0.055em',
        },
      },
    },

    MuiTableRow: {
      styleOverrides: {
        root: {
          transition: 'background-color 0.15s ease',

          '&:last-child td': {
            borderBottom: 0,
          },

          '&:hover': {
            backgroundColor: 'rgba(255, 255, 255, 0.025)',
          },
        },
      },
    },

    MuiOutlinedInput: {
      styleOverrides: {
        root: {
          borderRadius: 10,
          backgroundColor: '#26282D',

          '& .MuiOutlinedInput-notchedOutline': {
            borderColor: '#41454C',
          },

          '&:hover .MuiOutlinedInput-notchedOutline': {
            borderColor: '#737B86',
          },

          '&.Mui-focused .MuiOutlinedInput-notchedOutline': {
            borderColor: '#16B9CF',
            borderWidth: 1,
          },
        },
      },
    },

    MuiInputLabel: {
      styleOverrides: {
        root: {
          color: '#A7ADB7',
          '&.Mui-focused': {
            color: '#16B9CF',
          },
        },
      },
    },

    MuiSelect: {
      styleOverrides: {
        icon: {
          color: '#A7ADB7',
        },
      },
    },

    MuiMenu: {
      styleOverrides: {
        paper: {
          backgroundColor: '#303339',
          border: '1px solid #41454C',
          backgroundImage: 'none',
        },
      },
    },

    MuiMenuItem: {
      styleOverrides: {
        root: {
          '&.Mui-selected': {
            backgroundColor: 'rgba(22, 185, 207, 0.12)',
          },

          '&.Mui-selected:hover': {
            backgroundColor: 'rgba(22, 185, 207, 0.18)',
          },
        },
      },
    },

    MuiDialog: {
      styleOverrides: {
        paper: {
          backgroundColor: '#2D2D2D',
          backgroundImage: 'none',
          border: '1px solid #41454C',
          borderRadius: 16,
        },
      },
    },

    MuiChip: {
      styleOverrides: {
        root: {
          borderRadius: 8,
          fontWeight: 600,
        },

        colorDefault: {
          backgroundColor: '#41454C',
          color: '#E0E4EA',
        },
      },
    },

    MuiSwitch: {
      styleOverrides: {
        switchBase: {
          '&.Mui-checked': {
            color: '#16B9CF',
          },

          '&.Mui-checked + .MuiSwitch-track': {
            backgroundColor: '#16B9CF',
            opacity: 0.55,
          },
        },
      },
    },

    MuiAlert: {
      styleOverrides: {
        root: {
          borderRadius: 10,
        },
      },
    },

    MuiTooltip: {
      styleOverrides: {
        tooltip: {
          backgroundColor: '#41454C',
          fontSize: '0.8rem',
        },
      },
    },
  },
});

export default theme;
