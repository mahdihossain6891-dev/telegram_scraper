# Dashboard override — Telegram Scraper

Overrides `MASTER.md` for the live OSINT ops dashboard (Streamlit + Vercel).

## Mode

**Dark only** (ops / security monitoring). Light MASTER tokens are reference only.

## Tokens (implemented)

| Role | Hex | Notes |
|------|-----|-------|
| Background | `#020617` | Near-black ops canvas |
| Surface | `#0B1220` | Sidebar / panels |
| Surface elevated | `#111827` | KPI cards, tables |
| Primary | `#3B82F6` | Data / selection |
| Accent | `#D97706` | Alerts, live pulse, CTAs |
| Success | `#16A34A` | Healthy / live |
| Destructive | `#DC2626` | Critical flags |
| Foreground | `#E5EEFB` | Body text ≥ 4.5:1 |
| Muted | `#94A3B8` | Labels, captions |
| Border | `#334155` | Hairlines only |

## Typography

- Headings / brand: **Fira Code**
- Body / UI: **Fira Sans**
- Base size: 15–16px; dense tables 13–14px
- Line-height: 1.45–1.5

## Layout

- Sticky left rail (~280px), content fluid
- Density 8/10: 8–16px gaps, compact KPI grid
- Status strip above content: source · last export · live refresh
- Page = one H1 + metrics first, then charts/tables

## Interaction

- Transitions 150–250ms (no bounce on tables)
- Row hover highlight; focus rings use `--color-ring`
- `prefers-reduced-motion: reduce` disables stagger
- Charts: line/bar primary; avoid pie as sole category view

## Anti-patterns

- No emoji icons
- No ornate glass/glow stacks
- Do not remove filters
- Do not rely on color alone for categories (labels + legend)
