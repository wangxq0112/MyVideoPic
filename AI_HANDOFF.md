# MyVideoPic AI Handoff

This file is the working contract for an AI assistant continuing development of MyVideoPic. Read it together with `README.md` and `AGENTS.md` before changing code.

## Product Intent

MyVideoPic is a local, single-user Windows media library for videos and photos. It indexes user-selected folders without uploading data or relying on cloud services. The user expects a compact desktop-oriented interface, Chinese copy, and direct control over media files.

Core workflows:

- Select a media folder through the Windows native folder picker. Detect video and photo content, create the appropriate libraries, and scan them automatically.
- Browse the video and photo libraries with server-side filtering, ordering, and explicit pagination.
- Play browser-compatible videos in the page. Always preserve actions to copy the local path and open the file with the Windows default associated player (the user uses MPC-BE as the default player).
- Browse images at original resolution in the image viewer.
- Rename, move, and permanently delete real files only after confirmation.

## Non-Negotiable Constraints

- Local/offline only. Do not add telemetry, CDNs, external fonts, remote APIs, or cloud storage.
- Media folders are read-only during scan. The only operations that modify an original file are user-initiated rename, move, and permanent delete.
- Delete is irreversible and must remove the physical media file, its thumbnail, and its database record. Keep the confirmation flow.
- Local file-system paths must not appear in browser media URLs. Use UUID-based API endpoints.
- The UI and deployment target are Windows. Native folder picking and default-player launching are backend responsibilities.
- Browser capability decides embedded playback. MKV can play only when the current Edge/Chrome supports its exact container and codec combination. Do not hardcode MKV as always supported or always unsupported.
- Scans are manually initiated, except immediately after selecting a new library. Only one scan can run at a time. When a picker request arrives during a scan, wait for it and start a follow-up scan so the newly selected library is not missed.

## Architecture

| Area | Main locations | Responsibility |
| --- | --- | --- |
| Backend API | `backend/videos/views.py`, `urls.py` | Django REST endpoints, native picker, playback launch, list filtering |
| Scanner | `backend/videos/scanner.py` | Background incremental scans and task progress |
| File operations | `backend/videos/file_ops.py` | Rename/move/permanent deletion and thumbnail cleanup |
| Models | `backend/videos/models.py` | SQLite media libraries, videos, photos, favorites, history, scan records |
| Streaming | `backend/videos/streaming.py` | HTTP Range responses and optional Nginx `X-Accel-Redirect` |
| Frontend API | `frontend/src/api/api.js` | All client requests; keep endpoints centralized |
| Media state | `frontend/src/stores/media.js` | Shared Pinia pagination, filters, list actions |
| Main views | `frontend/src/views/Videos.vue`, `Images.vue`, `Player.vue` | Media grids, player, playlist, viewer interactions |
| Shared components | `frontend/src/components/` | Cards, grid, toolbar, dialogs, pagination, viewer |
| Styles | `frontend/src/style.css` | Handwritten design system using the `mv-` prefix |

## Current Behavior To Preserve

- Video and image lists use server-side pagination with 24 items per page. The user changes pages using the bottom pagination control; do not restore infinite scrolling.
- The video player playlist is scoped to the current video library and uses the same active `videos.filters.ordering` sort value as the main video library.
- The playlist shows a thumbnail, title, duration, and file size. Its next-video action follows that list and displays a localized end-of-playlist notice at the end.
- Deleting in the player chooses the next playlist item before opening the existing delete confirmation. On confirmed success, the video store refreshes and navigation goes to that next video; it returns to `/videos` only when there is no next item.
- The top-bar plus icon invokes `POST /libraries/pick-and-scan/`. It refreshes the visible video/photo page both initially and when scanning completes.
- Settings still contains the library-management entry point. Do not remove it when modifying the top-bar import flow.
- The image viewer supports original-size viewing, rotation, zoom, keyboard navigation, and path-independent image URLs.

## Data And API Notes

- `GET /api/videos/` and `GET /api/photos/` accept `library`, `category`, `favorited`, `q`, `ordering`, `page`, and `page_size`.
- Pagination responses are Django REST Framework objects: `count`, `next`, `previous`, `results`. The frontend deliberately does not use the absolute `next` URL.
- `backend/videos/pagination.py` has a server maximum page size of 200. The main grid asks for 24; the player may ask for 200 for its side playlist.
- `POST /api/videos/<uuid>/open/` opens the file through Windows file association. The frontend must never choose an executable player.
- `DELETE /api/videos/<uuid>/delete/` performs permanent deletion. Reuse `stores/ops.js` plus `MediaDialogs.vue` for confirmation.

## Development Guidance

- Prefer existing Pinia stores and API helpers over local duplicate requests.
- Keep backend filtering and ordering authoritative. Do not re-sort paginated pages in the browser.
- Preserve responsive behavior: the player playlist becomes a lower section on narrow screens.
- Use existing `Icon.vue` paths and `mv-icon-btn` for icon-only actions. Do not introduce an icon framework unless the project explicitly adopts one.
- Add focused tests when a behavior crosses API, file-system, or deletion boundaries. For normal frontend changes, run `npm run build` from `frontend`.
- Do not install or configure runtimes unless the user explicitly requests it.

## Delivery Rules

- `AGENTS.md` is mandatory: every completed repository change must be verified, committed, and pushed to `origin/main`.
- Work may begin on another branch, but finished scoped commits must be merged into local `main` and then pushed to `origin/main`.
- Do not stage or revert unrelated user changes.
- The user may request a release tag. Create an annotated tag on the completed `main` commit and push it explicitly, for example `git tag -a v0.2.0 -m "v0.2.0"` followed by `git push origin v0.2.0`.

## Validation Checklist

1. Run `git diff --check`.
2. Run `npm run build` from `frontend`.
3. Run Python syntax checks only when backend files change. The available local Python runtime may not be on `PATH`.
4. Inspect the task-scoped diff and `git status --short`.
5. Commit and push `main`; create and push any requested release tag.
