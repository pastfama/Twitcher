# Twitcher Development Workflow

This workspace uses two separate git worktrees so stable `main` app runs independently from active `dev` work.

## Worktrees

- `c:\Tools\Twitcher` — active development worktree on `dev`
- `c:\Tools\Twitcher-main` — stable worktree on `main`

## Launch scripts

### Dev workflow

Use the dev watch launcher in the dev worktree:

- `c:\Tools\Twitcher\start_twitcher_watch.bat`

This launches the app with `TWITCHER_WATCH=1`, so it exits when local Python files change.

### Stable main app

Use the stable launcher in the main worktree:

- `c:\Tools\Twitcher-main\start_twitcher.bat`

This launches the app from the stable `main` branch workspace.

### Main watch mode (optional)

Use this only if you want to run the main branch in watch mode:

- `c:\Tools\Twitcher-main\start_twitcher_watch.bat`

## Recommended flow

1. Work in `c:\Tools\Twitcher` on branch `dev`.
2. Use `start_twitcher_watch.bat` in that folder for live local reload.
3. When you want to update stable app:
   - merge `dev` into `main`
   - push `main` to GitHub
   - restart the stable app from `c:\Tools\Twitcher-main\start_twitcher.bat`

## Notes

- Local file edits trigger the watcher only in the dev worktree.
- Stable main app does not automatically follow GitHub updates.
- This setup keeps stable runtime separate from active development work.
