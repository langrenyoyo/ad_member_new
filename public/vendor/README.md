# Export dependencies

- `jquery.min.js`: jQuery 3.6.0, https://cdn.jsdelivr.net/npm/jquery@3.6.0/dist/jquery.min.js
  License: `jquery-LICENSE` (MIT).
- `tableExport.js`: tableExport.jquery.plugin 1.10.26 (minified upstream distribution), https://cdn.jsdelivr.net/npm/tableexport.jquery.plugin@1.10.26/tableExport.min.js
  License: `tableExport-LICENSE` (MIT).

Downloaded on 2026-09-12. Export dependencies load locally on demand; jQuery is shared with the date picker. jQuery's `noConflict()` preserves the application's existing `$` helper.

The reference site's jQuery response contained third-party script loading code, so it was replaced with the upstream distribution before browser execution. No reference-site dependency is executed by the local export flow.

Date-range dependencies (loaded locally when a date field receives focus):

- `daterangepicker.js`, `daterangepicker.css`: bootstrap-daterangepicker 2.1.27 from https://cdn.jsdelivr.net/npm/bootstrap-daterangepicker@2.1.27/ . MIT license text is included in `daterangepicker-README.md`.
- `moment.min.js`: Moment 2.29.4 from https://cdn.jsdelivr.net/npm/moment@2.29.4/min/moment.min.js . MIT license is included in `moment-LICENSE`.

Date selection and export share one jQuery loading promise to avoid duplicate loads and global helper conflicts.

Agent dashboard chart:

- `echarts.min.js`: ECharts 4.9.0 from https://cdn.jsdelivr.net/npm/echarts@4.9.0/dist/echarts.min.js . License retained in `echarts-LICENSE`.
- `echarts-walden.json`: theme configuration extracted as JSON from the reference site's `assets/js/echarts-theme.js`; no reference JavaScript is executed. Reference ECharts runtime version was 4.9.0.
- `china-map.js`: unmodified China geometry from https://github.com/echarts-maps/echarts-countries-js/blob/master/echarts-countries-js/china.js . Distributed separately under ODbL; license in `china-map-LICENSE`. Its geography is not evidence of the reference service's member-location rules. Upstream attribution is shown below the map.
