# Design System Master File

> **LOGIC:** When building a specific page, first check `design-system/telegram-scraper/pages/[page-name].md`.
> If that file exists, its rules **override** this Master file.

---

**Project:** Telegram Threat Console  
**Theme:** Dark / light glassmorphism SOC dashboard (premium)  
**Generated:** 2026-07-21  
**Category:** Threat Intelligence Dashboard  
**Design Dials:** Variance 6/10 | Motion 5/10 | Density 7/10  

---

## Global Rules

### Theme system

- `data-theme="dark" | "light"` on `<html>` via `ThemeProvider`
- Persist `localStorage` key `threat-console.theme`; init from `prefers-color-scheme`
- Prefer CSS variables — never hardcode page chrome hex when a token exists

### Color Palette (dark default)

| Role | Dark | Light | CSS Variable |
|------|------|-------|--------------|
| Background | `#0b0b12` | `#f4f5f9` | `--color-background` |
| Surface (glass) | `rgba(24,24,36,0.72)` | `rgba(255,255,255,0.86)` | `--color-surface` |
| Foreground | `#f1f5f9` | `#0f172a` | `--color-foreground` |
| Primary / accent | `#a78bfa` / `#8b5cf6` | `#7c3aed` | `--color-primary` / `--color-accent` |
| Secondary | `#818cf8` | `#6366f1` | `--color-secondary` |
| Muted | `#94a3b8` | `#64748b` | `--color-muted` |
| Border | `rgba(148,163,184,0.12)` | `rgba(15,23,42,0.08)` | `--color-border` |
| Success / Low | `#34d399` | `#10b981` | `--color-success` |
| Warning / Medium | `#fbbf24` | `#f59e0b` | `--color-warning` |
| High | `#fb923c` | `#f97316` | `--color-high` |
| Critical | `#f87171` | `#ef4444` | `--color-destructive` |
| Glow | purple neon | soft purple | `--color-glow` / `--shadow-glow` |

### Typography

- **Display:** Plus Jakarta Sans (`--font-jakarta`)
- **Body:** Inter (`--font-inter`)
- **Mono:** IDs, timestamps, Telegram IDs

### Layout (SOC shell)

- Collapsible sidebar (`--sidebar-width` / `--sidebar-collapsed`)
- Glass cards: blur + border + hover lift (`150–250ms`)
- Navbar: page title (SOC label) + source badge + live / collection / risk strip
- Settings drawer: Scope filters + Live refresh (do not remove)
- Nav labels map to existing pages: Dashboard→Command, Threat Monitoring→Intel, Alerts→Ops, Channels→Sources, Users→Cases
- Extra routes stay first-class: Behavioral (`/behavioral-analytics`), Sébastien (`/ai`), Threat Simulation

### Charts (ECharts)

- Theme-aware via CSS vars / `withThemeColors` / `ThreatChart`
- Smooth area lines, severity donut, purple heatmap ramp
- Tooltips use `--color-chart-tooltip-*`

### Motion

- Card hover lift, sidebar width transition, theme token cross-fade
- Respect `prefers-reduced-motion`

### Anti-patterns

- No Tailwind migration (CSS variables only)
- No new chart libraries
- No removing pages, filters, refresh, or API proxies
- No backend / scraper / AI planner changes for UI work
