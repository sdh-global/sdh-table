# Changelog

## 2.4.0

Changes since Release 2.3.2 - Add unique constraint for default profile.

### Added
- `Meta.default_sorting` option on `TableView`, plus `TableController.is_sorted`;
  applied automatically when the user hasn't picked a sort order via `?sort_by=`.
- `is_target_blank` option on `HrefWidget` / `ConditionHrefWidget` to render the
  link with `target="_blank"`.
- `README.md` with usage documentation and concepts.

### Changed
- Dropped support for Python < 3.11 and Django < 5.2. Now requires
  `Django>=5.2` and `Python>=3.11`.
- Verified compatibility with Django 5.2 and Python 3.13.

## 2.3.2

- Added a unique constraint preventing more than one default `TableViewProfile`
  per user/table.
