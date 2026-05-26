# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repository is

This is the **public release / distribution channel** for **JWSteel 통합전산** — the
in-house accounting / sales / purchasing / inventory ERP for **(주)정원철강
(Jeongwon Steel)**. It is **not** the application source repository.

The only tracked file is `README.md`. The actual deliverables live in **GitHub
Releases**: each release carries a Windows installer asset
(`JWSteel_Setup_vX.Y.Z.exe`) plus Korean-language release notes. All version
tags (`v3.0.3` … `v3.0.12` …) point at the same single commit — tags here are
release markers, not branch history. The application code is **not** in this
repo.

Consequently there is **no build, lint, or test step in this repo**, and no
source tree to navigate. Do not invent or run build/test tooling here. Work in
this repo is limited to:
- Editing `README.md`
- Authoring / correcting GitHub Release notes and tags
- Keeping version references consistent (see below)

Use the GitHub MCP tools (`mcp__github__*`) for release/tag/PR operations — the
`gh` CLI is not available.

## Release & versioning conventions

- **Tag format:** `vX.Y.Z` (semantic-ish; the line has stayed on `3.0.Z`).
- **Release title format:** `JWSteel 통합전산 vX.Y.Z (한 줄 요약)`.
- **Installer asset name:** `JWSteel_Setup_vX.Y.Z.exe`, attached to the release.
- **Release notes are written in Korean** and follow a consistent structure —
  `## vX.Y.Z — 요약`, then `### 추가` (added) / `### 수정` (fixed) /
  `### 설치` (install) sections. New notes should match this style.
- The standard install section states two paths: existing users update in-app
  via the **[업데이트]** menu (works from v3.0.4+); first-time users download
  the `.exe` and run the wizard.
- `README.md` is also Korean. Note: it currently hard-codes
  `JWSteel_Setup_v3.0.0.exe` in the install steps while the latest release is
  far ahead — keep that version reference in sync when bumping releases.

## How the app consumes this repo (context for release work)

The desktop app ships an **in-app auto-updater** that reads this repo's
releases. The intended flow (per the v3.0.4 notes) is: detect newer release →
[지금 업데이트] → download the `.exe` → silent install (Inno Setup) → auto
restart. Because of this, release hygiene matters more than usual:
- The frozen EXE reads its own version from `_internal/VERSION.txt`; a mismatch
  between that and the published tag previously caused an infinite "update
  available" loop (fixed in v3.0.4). Keep tag, asset filename, and the app's
  embedded version aligned when cutting a release.
- The Inno Setup `[Run]` section must not carry `skipifsilent`, or silent
  (in-app) installs won't auto-restart the app (v3.0.4 fix).

## Application context (for understanding release notes)

The packaged app — built elsewhere — is a **PyQt desktop ERP** (release notes
reference `QTableWidget`, dialogs, `showEvent`), **PyInstaller-frozen**, wrapped
in an **Inno Setup** installer, targeting **Windows 10/11 64-bit**. Data lives
in **Supabase (cloud)** plus a local **SQLite** store (e.g. the `inventory`
table loaded from `재고현황.xls`). Access is governed by **role-based menu
permissions** (e.g. roles 일반/임원 granted `sales_register`, `inventory`,
`outbound`).

Domain vocabulary that recurs in release notes:

| Korean | Meaning |
| --- | --- |
| 매출 | sales | 
| 매입 | purchase |
| 재고 | inventory / stock |
| 출고 | outbound / shipping |
| 수금 / 미수금 | collection / receivables |
| 거래처 | client / counterparty |
| 보관품 | consigned / stored goods (vs. 자사 = own stock) |
| 거래명세서 | transaction statement (PDF) |
| 단가 / 공급가 | unit price / supply amount |

These describe the app you are writing release notes *for*; the corresponding
source is not present in this repository.
