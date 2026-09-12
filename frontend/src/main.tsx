import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { HashRouter } from 'react-router-dom'
import './index.css'
import { App } from './App'

// HashRouter: the asset contract serves exact paths with no SPA rewrite, so every
// deep link lives under `#/…` and resolves to index.html on refresh and share.
createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <HashRouter>
      <App />
    </HashRouter>
  </StrictMode>,
)
