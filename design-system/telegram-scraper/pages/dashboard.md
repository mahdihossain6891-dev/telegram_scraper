# Dashboard override — Telegram Scraper

Overrides `MASTER.md` for the live OSINT analytics dashboard (Next.js + FastAPI).

## Mode

**Light Soft-UI** (Growlytics-inspired). Dark ops tokens are retired for the default theme.

## First viewport composition

1. Sidebar brand + nav groups  
2. Page title + live status  
3. Four KPI cards  
4. Activity line chart + peak-hours heatmap  
5. Personnel / channel table with risk bars  

## Tokens (implemented)

| Role | Hex |
|------|-----|
| Background | `#F4F5F9` |
| Surface | `#FFFFFF` |
| Primary | `#6D5EF6` |
| Primary soft | `#EEF0FF` |
| Success | `#10B981` |
| Destructive | `#EF4444` |
| Foreground | `#1F2937` |
| Muted | `#6B7280` |
| Border | `#E5E7EB` |

## Charts

Plotly light theme: purple line/bars, soft heatmap scale, muted axes, no dark template.
