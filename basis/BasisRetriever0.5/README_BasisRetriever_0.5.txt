
BasisRetriever
---------------

https://sourceforge.net/projects/basisretriever/

http://richk.net/wiki/BasisRetriever

This application may be modified and redistributed under the BSD license. See License.txt for specifics.

This program written under Python Portable v2.7.6.1 (for windows), which contains all external modules.  There are no other dependencies.  Executables created by py2exe.

To run Basis Retriever, extract the zip file into any folder. Browse to the app subfolder and run BasisRetriever.exe.  This is a portable application (http://en.wikipedia.org/wiki/Portable_application).

=================

Release Notes

v0.5 (2015-04-25): Simplified user interface: configuration parameters are now in a toggleable pane within the application, other options are now available in BasisRetriever.cfg within the app directory. Removed option for json-only download (no csv). Json storage directory is now set in BasisRetriever.cfg (no longer in UI). Fixed bug where daily data not updated correctly after adjust storage directory in the UI. 

Please re-enter your user inforamation and storage directory when start BasisRetriever for the first time after download.

v0.4 (2014-10-05): Updated basis website retrieval to account for changes in their API.  Added "Only D/L complete days" checkbox to prevent partial days from being saved.  Downloaded days that are incomplete (i.e., where watch data has not yet been uploaded to Basis website) are highlighted in orange text.  Added "Sync" button to retrieve data for any prior missing days, instead of clicking each date individually.

v0.3 (2014-03-31): Optional capability to add sleep events and activities to metrics csv file via "Add actys to metrics" checkbox.  When this is checked, sleep event download buttons are hidden because data is contained in metrics.  Configurable json file storage directory.  Command line version now works (via basis_retr.py).  Application now uses existing json files if they exist to create csv file (can be overriden with "cache override" checkbox).  Can now customize csv columns by modifying "cfg.json" file.   Date and time now available in 3 formats for csv files (via cfg.json): 1) datetime in a single string, 2) separate date and time fields, 3) python timestamp (seconds since 1 Jan 1970 at 00:00:00).  Several bug fixes and refactoring.

v0.2 (2014-03-03): Refactored code, added daily sleep events downloading. csv + json for both sleep and metrics.  Summary data (metrics and activities) now download a month at a time. View files by clicking on file size (blue underline). Fixed event handlers for option (drop-down) menus. Weekend days highlighted in yellow. Improved data validation before hitting basis's servers. Improved os-x compatibility.

v0.1.1 (2014-02-19): Fixed critical bug- fixed method/class naming problem

v0.1 (2014-02-18): initial release
