import { BrowserRouter } from 'react-router-dom';
import { NewsProvider } from './context/NewsContext';
import { ThemeProvider } from './context/ThemeContext';
import AppRoutes from './routes';

export default function App() {
  return (
    <ThemeProvider>
      <BrowserRouter>
        <NewsProvider>
          <AppRoutes />
        </NewsProvider>
      </BrowserRouter>
    </ThemeProvider>
  );
}
