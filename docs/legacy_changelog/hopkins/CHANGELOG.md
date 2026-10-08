# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.0.7] - 2026-06-29

### ✨ Added
- Added standard builder pages for **Products** (`page_7c0670bd`) and **Heritage** (`page_d146c1b5`).
- Integrated custom quantity selection buttons with custom CSS angled clip-paths on the Products page.
- Created a fully responsive chronological timeline list on the Heritage page.

### 🔧 Changed
- Fixed navbar responsiveness by hiding the mobile hamburger menu icon (`gd6hb44rx`) on desktop viewport sizes via standard base styles inside `hopkins_navbar.json`.
- Refactored page container styles, padding, margins, flex wrapping, and mobile styles across the Home (`page_e186e7f8`), About Us (`page_d80620c4`), and Contact Us (`page_e5ee16a2`) pages to improve tablet and mobile layouts.

### 🐛 Fixed
- Fixed a timing bug where elements with the `.fade-3d` transition class remained invisible (`opacity: 0`) due to the trigger script waiting on `window.load` after the DOM was already ready. Added a fallback to execute the animation trigger immediately if `document.readyState` is already interactive or complete.

## [0.0.6] - 2026-06-04

### ✨ Added
- Integrated modern 3D fade-in transitions (`fade-3d` animations) with custom offsets and delays across the main page structures (Home, About Us, and Contact Us) to enhance responsiveness and visual aesthetics.

### 🔧 Changed
- Standardized Builder JSON schemas across website components (Hero, Navbar) and pages (Home, About Us, Contact Us) with default attributes (`children`, `draggable`, `innerText`, `elementBeforeConversion`).
- Refactored page header text on the About Us page by converting HTML `<br>` tags to standard newlines (`\n`) for cleaner rendering.
- Adjusted mobile layout styling parameters (such as `position` and viewport alignment attributes) on page elements to ensure cross-device consistency.
- Updated internal asset index tracking (`idx`) for CSS and JavaScript Builder client scripts.

## [0.0.5] - 2026-06-04

### ✨ Added
- Integrated `Auto Tag and Release` GitHub Actions pipeline at `.github/workflows/tag_and_release.yml` to automatically tag commits and publish releases when a Pull Request is merged into version-16.

### 🔧 Changed
- Upgraded the Node.js setup version to `24` in `.github/workflows/ci.yml` to support Frappe version-16.
- Refactored `Case Study` DocType controller in `case_study.py` to inherit from `Document` instead of `WebsiteGenerator`, and disabled standard website generators in `case_study.json`.
- Updated naming configurations for `Case Study` and `Trusted Client` DocTypes to use `By fieldname` naming rules.
- Enabled data importing (`allow_import`) for `Case Study`, `Client Testimonial`, and `Trusted Client` DocTypes.
- Modified `bg_color` and set `logo_url` for the Hopkins Desktop Icon to enhance branding.
- Removed list view flags (`in_list_view`) from `Case Study` (image field) and `Trusted Client` (logo field) DocType structures.

### 🐛 Fixed
- Resolved AttributeError during Case Study validation/import by removing obsolete `super().validate()` and `super().make_route()` calls from the `CaseStudy` document class.

## [0.0.4] - 2026-06-04

### ✨ Added
- Created the whitelisted guest-accessible API endpoint `/api/method/hopkins.api.subscribe_newsletter` in `api.py` for guest/visitor newsletter subscriptions.
- Implemented backend handling to automatically verify and create the "Newsletter" `Email Group` and insert new subscribers into the `Email Group Member` DocType with duplicate email validation.

### 🔧 Changed
- Injected client-side JavaScript logic into the "Newsletter Form" builder block (ID: `ibhohj006`) within the HOPKINS Footer Section component (`hopkins_footer_section.json`).
  - Added input validation for email address.
  - Set up asynchronous JSON POST request to the newsletter subscription API endpoint.
  - Included CSRF token handling via the `X-Frappe-CSRF-Token` header.
  - Added visual user feedback using Toastify notifications for successful subscriptions, duplicate emails, and server/validation errors.
  - Handled button state disabling and input field clearing on successful subscription.
- Synchronized updated footer layout, navbar, client scripts, page files, and JSON configurations back to the site database.

## [0.0.3] - 2026-06-04

### ✨ Added
- Created `Case Study` DocType with title, route, image, short description, content, and dedicated SEO metatags (meta title, description, image).
- Implemented `/api/method/hopkins.api.get_case_studies` whitelisted API endpoint to retrieve published case studies.
- Configured dynamic detail page rendering with an elegant template at `templates/generators/case_study.html` using clean, modern typography.
- Integrated the database query `data.case_studies` into the Home-2 builder page's server-side script.

## [0.0.2] - 2026-06-03

### ✨ Added
- Created `Client Testimonial` DocType with `person_name`, `trusted_client` link, `description`, and `publish_to_website` fields.
- Implemented `/api/method/hopkins.api.get_testimonials` whitelisted endpoint for client testimonials.
- Integrated backend testimonial queries into builder page server-side data scripts.

### 🐛 Fixed
- Resolved testimonial slider layout clipping and blank display issues by applying structural CSS overrides (`display: flex !important` and width/flex flex-shrink settings) to override default builder layout styles on track and slide elements.

## [0.0.1] - 2026-06-01

### ✨ Added
- Programmatic page generation scripts for Blinds, Gallery, Heritage, and Team pages using native Frappe Builder JSON blocks.
- Responsive design definitions supporting desktop serpentine timeline loops and mobile stacked timelines.
- Automated CI testing workflow (`ci.yml`) setting up MariaDB, Redis, and bench testing.
- Pull request linter workflow (`linter.yml`) for Semgrep scanning, dependency auditing, and pre-commit checks.
- Pre-commit configuration (`.pre-commit-config.yaml`) for local whitespace, ruff linter, prettier, and eslint execution.
