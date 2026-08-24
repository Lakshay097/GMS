# DESIGN INVENTORY

## GLOBAL DESIGN SYSTEM

### Color Palette

#### Primary Colors (CSS Variables from index.css)
- `--ink: #0b3b3a` - Primary dark ink color
- `--ink-soft: #1a4f4d` - Softer ink variant
- `--text: #3d5553` - Primary text color
- `--text-h: #0f2e2d` - Heading text color
- `--text-muted: #6b8582` - Muted text color
- `--bg: #eef5f3` - Background color
- `--bg-deep: #dce9e5` - Deep background variant
- `--surface: rgba(255, 255, 255, 0.78)` - Surface color with transparency
- `--surface-solid: #ffffff` - Solid surface color
- `--border: rgba(11, 59, 58, 0.12)` - Border color
- `--border-strong: rgba(11, 59, 58, 0.22)` - Strong border color

#### Accent Colors
- `--accent: #c9922a` - Primary accent (gold)
- `--accent-hover: #b07e1f` - Accent hover state
- `--accent-soft: rgba(201, 146, 42, 0.14)` - Soft accent background
- `--accent-ink: #7a5610` - Accent ink color

#### Status Colors
- `--success: #1f7a5c` - Success green
- `--success-bg: #e4f5ee` - Success background
- `--danger: #b53a3a` - Danger red
- `--danger-bg: #fceaea` - Danger background
- `--warning: #9a6b12` - Warning yellow
- `--warning-bg: #fff4d9` - Warning background

#### Reference Design Colors (Additional palette)
- `--ink-ref: #0F3B37` - Reference ink
- `--ink-2-ref: #12524B` - Reference ink variant
- `--paper-ref: #F6F3EC` - Paper background
- `--paper-2-ref: #EFEAE0` - Paper variant
- `--card-ref: #FFFFFF` - Card background
- `--line-ref: #E3DDCE` - Line/border color
- `--clay-ref: #C6793F` - Clay accent
- `--gold-ref: #C89B3C` - Gold accent
- `--moss-ref: #5C8A6E` - Moss green
- `--rose-ref: #B5533E` - Rose red
- `--slate-ref: #6B6459` - Slate gray
- `--slate-2-ref: #8A8375` - Slate variant

#### Component-Specific Colors
- Status pills: `#F2E7D6` (pending), `#DCEAE6` (progress), `#E4EDE0` (completed), `#F0DEDA` (review)
- Priority dots: `var(--rose-ref)` (high), `var(--gold-ref)` (medium), `var(--moss-ref)` (low)
- Buttons: Various states using the above color palette

### Typography

#### Font Families
- `--font-display: 'Syne', system-ui, sans-serif` - Display font for headings
- `--font-body: 'Figtree', system-ui, sans-serif` - Body font for content
- `--mono: ui-monospace, 'Cascadia Code', Consolas, monospace` - Monospace for code/data

#### Font Sizes
- Base: `16px` (1rem)
- Display: `clamp(4rem, 12vw, 7rem)` - Home page brand
- H1: `clamp(1.75rem, 3vw, 2.25rem)` - Main headings
- H2: `clamp(1.25rem, 2vw, 1.5rem)` - Section headings
- H3: `1.1rem` - Card headings
- Body: `0.925rem` - Table and form text
- Small: `0.875rem` - Labels and metadata
- Tiny: `0.75rem` - Badges and small tags

#### Font Weights
- Regular: `400` (default)
- Medium: `500` (labels, some text)
- Semibold: `600` (headings, buttons)
- Bold: `700` (display headings)

#### Letter Spacing
- Base: `0.01em`
- Headings: `-0.03em` to `-0.02em` (tighter spacing)
- Uppercase text: `0.04em` to `0.14em` (wider spacing)

### Spacing Scale

#### Padding/Margins
- `0.25rem` - 4px (tight spacing)
- `0.5rem` - 8px (small spacing)
- `0.65rem` - 10.4px (button padding)
- `0.75rem` - 12px (medium spacing)
- `1rem` - 16px (standard spacing)
- `1.25rem` - 20px (card padding)
- `1.5rem` - 24px (section spacing)
- `2rem` - 32px (large spacing)
- `2.5rem` - 40px (extra large spacing)

#### Grid Gaps
- `0.5rem` - 8px (tight grid)
- `0.75rem` - 12px (medium grid)
- `1rem` - 16px (standard grid)
- `1.25rem` - 20px (card grid)
- `1.5rem` - 24px (large grid)

### Border Radius
- `--radius: 12px` - Standard border radius
- `--radius-sm: 8px` - Small border radius
- `--radius-lg: 20px` - Large border radius
- `999px` - Fully rounded (pills, badges)

### Shadows
- `--shadow-sm: 0 1px 2px rgba(11, 59, 58, 0.06)` - Small shadow
- `--shadow: 0 8px 28px rgba(11, 59, 58, 0.08)` - Standard shadow
- `--shadow-lg: 0 20px 50px rgba(11, 59, 58, 0.12)` - Large shadow
- `--shadow-ref: 0 1px 2px rgba(15,59,55,0.04), 0 8px 24px -12px rgba(15,59,55,0.12)` - Reference shadow

### Animations
- `--ease: cubic-bezier(0.22, 1, 0.36, 1)` - Default easing
- `fade-up` - Fade in with upward movement
- `fade-in` - Simple fade in
- `soft-pulse` - Subtle opacity pulse
- `revolve` - 360-degree rotation
- `revolve-slow` - Slow 360-degree rotation
- `slide-down` - Slide down animation
- `spin` - Continuous rotation (loading)

### Component Library
- **No external component library** - Custom built components
- CSS-only components with React integration
- No Material UI, Ant Design, or similar libraries

### Icon Library
- **Emoji icons** used throughout (🏫, 📊, ✏️, 🗑️, ✓, ⚠️, etc.)
- No formal icon library like Lucide or Heroicons
- Unicode characters for simple icons (▶, ▼, +, ×)

### Layout Structure
- **Container**: `.app` - Main app container with flex column
- **Top Bar**: `.topbar` - Fixed height navigation bar (64px)
- **Main Content**: `.main` - Main content area with flex-1
- **Background**: `.bg-texture` - Fixed background pattern
- **Page Shell**: `.page-shell` - Page wrapper with fade-up animation

### Responsive behavior (CRITICAL — audit this carefully per screen)
- Does this screen currently have responsive/breakpoint logic? List exact breakpoints (px values) if defined in CSS/Tailwind config/media queries
- What changes at each breakpoint currently (columns collapse, sidebar hides, nav becomes hamburger, etc.)
- Flag anything that is CURRENTLY BROKEN or NOT HANDLED at smaller widths:
  - Tables/grids with many columns that have no mobile fallback
  - Fixed-width elements (px instead of %/rem/fr) that will overflow on small screens
  - Text or buttons that get cut off, truncated, or overlap at narrow widths
  - Modals/dropdowns/tooltips that may overflow viewport on mobile
  - Horizontal scroll present (intentional or accidental)
  - Touch target sizes (are buttons/links big enough for touch, or clearly mouse-only e.g. hover-only menus)
- Note the CSS framework/approach used for responsiveness (Tailwind breakpoints, CSS Grid, media queries, container queries, none)

Also add to the GLOBAL DESIGN SYSTEM section at the top:
- Full list of ALL breakpoints used anywhere in the app (px values)
- Whether the app uses a mobile-first or desktop-first CSS approach
- Any components that currently have ZERO responsive handling (will just break/overflow on small screens)

### Responsive Breakpoints
- Mobile: `max-width: 540px`
- Tablet: `max-width: 768px`
- Desktop: `max-width: 860px`
- Large screens: Default (no max-width)

---

## PAGE SCREENS

## Home — `/`

### Purpose
Landing page that provides navigation to authenticated users and sign-in/sign-up options for unauthenticated users.

### Layout Structure
- Full-height hero section with dark gradient background
- Animated background elements (glowing orbs)
- Centered content with brand name, headline, and CTA buttons
- Responsive design with different layouts for mobile vs desktop

### Responsive behavior (CRITICAL — audit this carefully per screen)
- Does this screen currently have responsive/breakpoint logic? List exact breakpoints (px values) if defined in CSS/Tailwind config/media queries
- What changes at each breakpoint currently (columns collapse, sidebar hides, nav becomes hamburger, etc.)
- Flag anything that is CURRENTLY BROKEN or NOT HANDLED at smaller widths:
  - Tables/grids with many columns that have no mobile fallback
  - Fixed-width elements (px instead of %/rem/fr) that will overflow on small screens
  - Text or buttons that get cut off, truncated, or overlap at narrow widths
  - Modals/dropdowns/tooltips that may overflow viewport on mobile
  - Horizontal scroll present (intentional or accidental)
  - Touch target sizes (are buttons/links big enough for touch, or clearly mouse-only e.g. hover-only menus)
- Note the CSS framework/approach used for responsiveness (Tailwind breakpoints, CSS Grid, media queries, container queries, none)

Also add to the GLOBAL DESIGN SYSTEM section at the top:
- Full list of ALL breakpoints used anywhere in the app (px values)
- Whether the app uses a mobile-first or desktop-first CSS approach
- Any components that currently have ZERO responsive handling (will just break/overflow on small screens)

### Components on This Page
- **Brand Display**: Large "GMS" text with gradient color effect
- **Headline Text**: Dynamic internationalized headline text
- **Support Text**: Welcome message for users
- **Sign In Button**: Primary button for authentication (SignedOut state)
- **Sign Up Button**: Accent button for registration (SignedOut state)
- **Dashboard Button**: Primary button linking to dashboard (SignedIn state)

### Visual Styling
- **Background**: Linear gradient `linear-gradient(135deg, #0f1a17 0%, #12524b 50%, #1a3a35 100%)`
- **Brand Font**: `var(--font-display)` with `clamp(4rem, 12vw, 7rem)` size
- **Brand Color**: White text with gold gradient `linear-gradient(135deg, #ffffff 0%, #c89b3c 100%)`
- **Headline Font**: `var(--font-display)`, `clamp(1.5rem, 3.5vw, 2.2rem)`, weight 600
- **Text Color**: `rgba(255, 255, 255, 0.9)` for headline, `rgba(255, 255, 255, 0.7)` for support
- **Button Styling**: Uses global `.btn` classes with primary/accent variants
- **Animation**: `fade-up` animation with staggered delays (0s, 0.15s, 0.25s, 0.35s)

### Navigation & Interactions
- **Sign In Button**: Opens Clerk authentication modal
- **Sign Up Button**: Opens Clerk registration modal
- **Dashboard Button**: Navigates to `/dashboard` route
- **Background Animation**: Continuous floating animation on glowing orbs

### Data Displayed
- No dynamic data - static content with internationalization support

---

## Auth — `/auth/*`

### Purpose
Authentication entry point with sign-in/sign-up functionality and complete signup flow.

### Layout Structure
- Centered card layout on light background
- Maximum width 440px with auto margins
- Vertical form layout with stacked elements

### Responsive behavior (CRITICAL — audit this carefully per screen)
- Does this screen currently have responsive/breakpoint logic? List exact breakpoints (px values) if defined in CSS/Tailwind config/media queries
- What changes at each breakpoint currently (columns collapse, sidebar hides, nav becomes hamburger, etc.)
- Flag anything that is CURRENTLY BROKEN or NOT HANDLED at smaller widths:
  - Tables/grids with many columns that have no mobile fallback
  - Fixed-width elements (px instead of %/rem/fr) that will overflow on small screens
  - Text or buttons that get cut off, truncated, or overlap at narrow widths
  - Modals/dropdowns/tooltips that may overflow viewport on mobile
  - Horizontal scroll present (intentional or accidental)
  - Touch target sizes (are buttons/links big enough for touch, or clearly mouse-only e.g. hover-only menus)
- Note the CSS framework/approach used for responsiveness (Tailwind breakpoints, CSS Grid, media queries, container queries, none)

Also add to the GLOBAL DESIGN SYSTEM section at the top:
- Full list of ALL breakpoints used anywhere in the app (px values)
- Whether the app uses a mobile-first or desktop-first CSS approach
- Any components that currently have ZERO responsive handling (will just break/overflow on small screens)

### Components on This Page
- **Heading**: "Sign In" or authentication title
- **Auth Form**: Clerk-provided authentication form
- **Sign In Button**: Primary button for sign-in
- **Sign Up Button**: Secondary button for registration
- **Auth Links**: Navigation between sign-in and sign-up
- **Complete Signup**: Special route for completing registration

### Visual Styling
- **Card Background**: `var(--card-ref)` (#FFFFFF)
- **Card Border**: `1px solid var(--line-ref)` (#E3DDCE)
- **Card Radius**: `20px`
- **Card Shadow**: `var(--shadow)` 
- **Heading Font**: `var(--font-display)`, `1.65rem`, weight 600
- **Heading Color**: `var(--ink-ref)` (#0F3B37)
- **Form Input Styling**: Standard form inputs with 1px borders, 8px radius
- **Button Styling**: Global button styles with primary/secondary variants

### Navigation & Interactions
- **Sign In**: Opens Clerk authentication modal
- **Sign Up**: Opens Clerk registration modal
- **Complete Signup**: Handles special signup completion flow
- **Form Validation**: Client-side validation with error messages

### Data Displayed
- No dynamic data - authentication UI only

---

## Account — `/account/*`

### Purpose
User account management page for profile settings and preferences.

### Layout Structure
- Centered layout with maximum width 760px
- Header section with user identity display
- Body section for account settings (to be implemented)

### Responsive behavior (CRITICAL — audit this carefully per screen)
- Does this screen currently have responsive/breakpoint logic? List exact breakpoints (px values) if defined in CSS/Tailwind config/media queries
- What changes at each breakpoint currently (columns collapse, sidebar hides, nav becomes hamburger, etc.)
- Flag anything that is CURRENTLY BROKEN or NOT HANDLED at smaller widths:
  - Tables/grids with many columns that have no mobile fallback
  - Fixed-width elements (px instead of %/rem/fr) that will overflow on small screens
  - Text or buttons that get cut off, truncated, or overlap at narrow widths
  - Modals/dropdowns/tooltips that may overflow viewport on mobile
  - Horizontal scroll present (intentional or accidental)
  - Touch target sizes (are buttons/links big enough for touch, or clearly mouse-only e.g. hover-only menus)
- Note the CSS framework/approach used for responsiveness (Tailwind breakpoints, CSS Grid, media queries, container queries, none)

Also add to the GLOBAL DESIGN SYSTEM section at the top:
- Full list of ALL breakpoints used anywhere in the app (px values)
- Whether the app uses a mobile-first or desktop-first CSS approach
- Any components that currently have ZERO responsive handling (will just break/overflow on small screens)

### Components on This Page
- **Account Page Header**: Contains user identity and navigation
- **User Button**: Clerk-provided user profile button
- **User Name**: Display user's full name
- **User Email**: Display user's email address
- **Account Settings Body**: Placeholder for account settings

### Visual Styling
- **Header Background**: Transparent with bottom border
- **Header Border**: `1px solid var(--line-ref)`
- **Name Font**: `var(--font-display)`, `1.2rem`, weight 700
- **Name Color**: `var(--ink-ref)`
- **Email Font**: `0.875rem` 
- **Email Color**: `var(--slate-2-ref)`
- **Card Normalization**: Clerk cards styled to match design tokens

### Navigation & Interactions
- **User Button**: Opens Clerk user profile menu
- **Account Settings**: Placeholder for future implementation

### Data Displayed
- **User Name**: From Clerk user object (`user?.fullName`)
- **User Email**: From Clerk user object (`user?.emailAddresses[0]?.emailAddress`)

---

## Schools — `/schools`

### Purpose
List view of all schools in the system with create, edit, and deactivate functionality.

### Layout Structure
- Header with title and "Create School" button
- Grid layout for school cards (responsive)
- Pagination controls at bottom
- Expandable card details

### Responsive behavior (CRITICAL — audit this carefully per screen)
- Does this screen currently have responsive/breakpoint logic? List exact breakpoints (px values) if defined in CSS/Tailwind config/media queries
- What changes at each breakpoint currently (columns collapse, sidebar hides, nav becomes hamburger, etc.)
- Flag anything that is CURRENTLY BROKEN or NOT HANDLED at smaller widths:
  - Tables/grids with many columns that have no mobile fallback
  - Fixed-width elements (px instead of %/rem/fr) that will overflow on small screens
  - Text or buttons that get cut off, truncated, or overlap at narrow widths
  - Modals/dropdowns/tooltips that may overflow viewport on mobile
  - Horizontal scroll present (intentional or accidental)
  - Touch target sizes (are buttons/links big enough for touch, or clearly mouse-only e.g. hover-only menus)
- Note the CSS framework/approach used for responsiveness (Tailwind breakpoints, CSS Grid, media queries, container queries, none)

Also add to the GLOBAL DESIGN SYSTEM section at the top:
- Full list of ALL breakpoints used anywhere in the app (px values)
- Whether the app uses a mobile-first or desktop-first CSS approach
- Any components that currently have ZERO responsive handling (will just break/overflow on small screens)

### Components on This Page
- **Page Header**: "Schools" heading with create button
- **Create School Button**: Primary button linking to `/schools/new`
- **School Cards**: Floating cards with school information
- **School Icon**: Emoji icon (🏫) for visual identification
- **School Name**: Link to edit page
- **School Code**: Display code in styled badge
- **Status Pill**: Color-coded status indicator
- **Expand Toggle**: Button to show/hide card details
- **Detail Sections**: Contact info, address, timeline
- **Edit School Button**: Primary button in card actions
- **Deactivate Button**: Danger button for active schools
- **Pagination**: Previous/Next navigation with page indicator

### Visual Styling
- **Header**: Uses global `.header` class with bottom border
- **Card Background**: `var(--card-ref)` (#FFFFFF)
- **Card Border**: `1px solid var(--line-ref)`
- **Card Radius**: `16px`
- **Card Shadow**: `var(--shadow-ref)`
- **School Icon**: `1.5rem` emoji
- **School Code**: Monospace font, `var(--paper-2-ref)` background
- **Status Pills**: Color-coded by status (active, inactive, etc.)
- **Button Styling**: Global button styles with size variants

### Navigation & Interactions
- **Create School**: Navigates to `/schools/new`
- **School Name Link**: Navigates to `/schools/{id}/edit`
- **Expand Toggle**: Shows/hides detailed school information
- **Edit School**: Navigates to edit page
- **Deactivate**: Triggers confirmation dialog and API call
- **Pagination**: Changes page with API call

### Data Displayed
- **School List**: Array of school objects from API
- **School Fields**: name, code, status, address, contact_email, contact_phone, created_at, deactivated_at
- **Pagination**: Current page, total count, page size (50)

---

## School Form — `/schools/new` and `/schools/:id/edit`

### Purpose
Create new school or edit existing school information.

### Layout Structure
- Header with title and back button
- Centered form card
- Vertical form layout with grouped fields
- Action buttons at bottom

### Responsive behavior (CRITICAL — audit this carefully per screen)
- Does this screen currently have responsive/breakpoint logic? List exact breakpoints (px values) if defined in CSS/Tailwind config/media queries
- What changes at each breakpoint currently (columns collapse, sidebar hides, nav becomes hamburger, etc.)
- Flag anything that is CURRENTLY BROKEN or NOT HANDLED at smaller widths:
  - Tables/grids with many columns that have no mobile fallback
  - Fixed-width elements (px instead of %/rem/fr) that will overflow on small screens
  - Text or buttons that get cut off, truncated, or overlap at narrow widths
  - Modals/dropdowns/tooltips that may overflow viewport on mobile
  - Horizontal scroll present (intentional or accidental)
  - Touch target sizes (are buttons/links big enough for touch, or clearly mouse-only e.g. hover-only menus)
- Note the CSS framework/approach used for responsiveness (Tailwind breakpoints, CSS Grid, media queries, container queries, none)

Also add to the GLOBAL DESIGN SYSTEM section at the top:
- Full list of ALL breakpoints used anywhere in the app (px values)
- Whether the app uses a mobile-first or desktop-first CSS approach
- Any components that currently have ZERO responsive handling (will just break/overflow on small screens)

### Components on This Page
- **Page Header**: "Create School" or "Edit School" with back button
- **Back Button**: Secondary button linking to `/schools`
- **Error Display**: Error message banner (if present)
- **Form Card**: Container for form fields
- **Name Input**: Required text input for school name
- **Code Input**: Required text input (disabled on edit)
- **Address Textarea**: Optional textarea for address
- **Contact Email Input**: Optional email input
- **Contact Phone Input**: Optional phone input
- **Cancel Button**: Secondary button to return to list
- **Submit Button**: Primary button with loading state

### Visual Styling
- **Form Card**: `var(--card-ref)` background, `1px solid var(--line-ref)` border, `16px` radius
- **Form Groups**: Standard spacing with labels above inputs
- **Label Styling**: `0.875rem`, weight 600, `var(--ink-ref)` color
- **Input Styling**: Full width, `0.75rem 1rem` padding, `1.5px solid var(--line-ref)` border, `10px` radius
- **Input Focus**: `var(--ink-ref)` border color with shadow
- **Input Disabled**: `var(--paper-2-ref)` background, not-allowed cursor
- **Error Banner**: Gradient background with danger colors

### Navigation & Interactions
- **Back Button**: Navigates to `/schools`
- **Cancel Button**: Navigates to `/schools`
- **Submit Button**: Creates/updates school via API, then navigates to list
- **Form Validation**: HTML5 required validation + API validation
- **Loading State**: Button shows "Saving..." during API call

### Data Displayed
- **Form Data**: name, code, address, contact_email, contact_phone
- **Edit Mode**: Pre-populated with existing school data
- **Create Mode**: Empty form with default values

---

## Departments — `/departments`

### Purpose
List view of all departments grouped by school with create and archive functionality.

### Layout Structure
- Header with title and "Create Department" button
- Table layout with school grouping
- Pagination info at bottom

### Responsive behavior (CRITICAL — audit this carefully per screen)
- Does this screen currently have responsive/breakpoint logic? List exact breakpoints (px values) if defined in CSS/Tailwind config/media queries
- What changes at each breakpoint currently (columns collapse, sidebar hides, nav becomes hamburger, etc.)
- Flag anything that is CURRENTLY BROKEN or NOT HANDLED at smaller widths:
  - Tables/grids with many columns that have no mobile fallback
  - Fixed-width elements (px instead of %/rem/fr) that will overflow on small screens
  - Text or buttons that get cut off, truncated, or overlap at narrow widths
  - Modals/dropdowns/tooltips that may overflow viewport on mobile
  - Horizontal scroll present (intentional or accidental)
  - Touch target sizes (are buttons/links big enough for touch, or clearly mouse-only e.g. hover-only menus)
- Note the CSS framework/approach used for responsiveness (Tailwind breakpoints, CSS Grid, media queries, container queries, none)

Also add to the GLOBAL DESIGN SYSTEM section at the top:
- Full list of ALL breakpoints used anywhere in the app (px values)
- Whether the app uses a mobile-first or desktop-first CSS approach
- Any components that currently have ZERO responsive handling (will just break/overflow on small screens)

### Components on This Page
- **Page Header**: "Departments" heading with create button
- **Create Department Button**: Primary button linking to `/departments/new`
- **Table Container**: Wrapped table with overflow handling
- **Data Table**: Standard table with headers and rows
- **School Header Rows**: Grouped rows showing school names
- **Department Name**: Link to edit page
- **Department Code**: Display code
- **Status Badge**: Color-coded status indicator
- **Description**: Display description or "-"
- **Created Date**: Formatted date string
- **Edit Button**: Small button for editing
- **Archive Button**: Danger button for active departments
- **Pagination Info**: Total count display

### Visual Styling
- **Table Container**: `var(--card-ref)` background, `1px solid var(--line-ref)` border, `16px` radius
- **Table Headers**: `var(--paper-ref)` background, uppercase text, `0.78rem` size
- **School Header**: `#f0f0f0` background, bold text
- **Status Badges**: Color-coded by status (active, inactive, etc.)
- **Link Styling**: `var(--ink-ref)` color, hover underline
- **Button Styling**: Global button styles with small variant

### Navigation & Interactions
- **Create Department**: Navigates to `/departments/new`
- **Department Name Link**: Navigates to `/departments/{id}/edit`
- **Edit Button**: Navigates to edit page
- **Archive Button**: Triggers confirmation dialog and API call
- **Table Hover**: Row background changes on hover

### Data Displayed
- **Department List**: Array of department objects grouped by school
- **Department Fields**: school_name, name, code, status, description, created_at
- **Grouping**: Departments grouped by school with header rows
- **Pagination**: Total count display (page size 200)

---

## Department Form — `/departments/new` and `/departments/:id/edit`

### Purpose
Create new department or edit existing department information.

### Layout Structure
- Header with title and back button
- Centered form card
- Vertical form layout with grouped fields
- Action buttons at bottom

### Responsive behavior (CRITICAL — audit this carefully per screen)
- Does this screen currently have responsive/breakpoint logic? List exact breakpoints (px values) if defined in CSS/Tailwind config/media queries
- What changes at each breakpoint currently (columns collapse, sidebar hides, nav becomes hamburger, etc.)
- Flag anything that is CURRENTLY BROKEN or NOT HANDLED at smaller widths:
  - Tables/grids with many columns that have no mobile fallback
  - Fixed-width elements (px instead of %/rem/fr) that will overflow on small screens
  - Text or buttons that get cut off, truncated, or overlap at narrow widths
  - Modals/dropdowns/tooltips that may overflow viewport on mobile
  - Horizontal scroll present (intentional or accidental)
  - Touch target sizes (are buttons/links big enough for touch, or clearly mouse-only e.g. hover-only menus)
- Note the CSS framework/approach used for responsiveness (Tailwind breakpoints, CSS Grid, media queries, container queries, none)

Also add to the GLOBAL DESIGN SYSTEM section at the top:
- Full list of ALL breakpoints used anywhere in the app (px values)
- Whether the app uses a mobile-first or desktop-first CSS approach
- Any components that currently have ZERO responsive handling (will just break/overflow on small screens)

### Components on This Page
- **Page Header**: "Create Department" or "Edit Department" with back button
- **Back Button**: Secondary button linking to `/departments`
- **Error Display**: Error message banner (if present)
- **Form Card**: Container for form fields
- **School ID Input**: Required text input (disabled on edit)
- **Name Input**: Required text input for department name
- **Code Input**: Required text input for department code
- **Description Textarea**: Optional textarea for description
- **Department Head Input**: Optional text input for user ID
- **Cancel Button**: Secondary button to return to list
- **Submit Button**: Primary button with loading state

### Visual Styling
- **Form Card**: `var(--card-ref)` background, `1px solid var(--line-ref)` border, `16px` radius
- **Form Groups**: Standard spacing with labels above inputs
- **Label Styling**: `0.875rem`, weight 600, `var(--ink-ref)` color
- **Input Styling**: Full width, `0.75rem 1rem` padding, `1.5px solid var(--line-ref)` border, `10px` radius
- **Input Focus**: `var(--ink-ref)` border color with shadow
- **Input Disabled**: `var(--paper-2-ref)` background, not-allowed cursor
- **Error Banner**: Gradient background with danger colors

### Navigation & Interactions
- **Back Button**: Navigates to `/departments`
- **Cancel Button**: Navigates to `/departments`
- **Submit Button**: Creates/updates department via API, then navigates to list
- **Form Validation**: HTML5 required validation + API validation
- **Loading State**: Button shows "Saving..." during API call

### Data Displayed
- **Form Data**: school_id, name, code, description, head_user_id
- **Edit Mode**: Pre-populated with existing department data
- **Create Mode**: Empty form with default values

---

## Users — `/users`

### Purpose
List view of all users with create, edit, and archive functionality.

### Layout Structure
- Header with title and "Create User" button
- Grid layout for user cards (responsive)
- Pagination controls at bottom
- Expandable card details

### Responsive behavior (CRITICAL — audit this carefully per screen)
- Does this screen currently have responsive/breakpoint logic? List exact breakpoints (px values) if defined in CSS/Tailwind config/media queries
- What changes at each breakpoint currently (columns collapse, sidebar hides, nav becomes hamburger, etc.)
- Flag anything that is CURRENTLY BROKEN or NOT HANDLED at smaller widths:
  - Tables/grids with many columns that have no mobile fallback
  - Fixed-width elements (px instead of %/rem/fr) that will overflow on small screens
  - Text or buttons that get cut off, truncated, or overlap at narrow widths
  - Modals/dropdowns/tooltips that may overflow viewport on mobile
  - Horizontal scroll present (intentional or accidental)
  - Touch target sizes (are buttons/links big enough for touch, or clearly mouse-only e.g. hover-only menus)
- Note the CSS framework/approach used for responsiveness (Tailwind breakpoints, CSS Grid, media queries, container queries, none)

Also add to the GLOBAL DESIGN SYSTEM section at the top:
- Full list of ALL breakpoints used anywhere in the app (px values)
- Whether the app uses a mobile-first or desktop-first CSS approach
- Any components that currently have ZERO responsive handling (will just break/overflow on small screens)

### Components on This Page
- **Page Header**: "Users" heading with create button
- **Create User Button**: Primary button linking to `/users/new`
- **User Cards**: Floating cards with user information
- **User Avatar**: Circle with user's initial
- **User Name**: Link to edit page
- **User Email**: Display email address
- **Status Pill**: Color-coded status indicator
- **Expand Toggle**: Button to show/hide card details
- **Roles Container**: Flex container for role badges
- **Role Badges**: Styled badges for each role
- **Detail Sections**: Assignment, additional info, timeline
- **Edit User Button**: Primary button in card actions
- **Archive Button**: Danger button for active users
- **Pagination**: Previous/Next navigation with page indicator

### Visual Styling
- **Header**: Uses global `.header` class with bottom border
- **Card Background**: `var(--card-ref)` (#FFFFFF)
- **Card Border**: `1px solid var(--line-ref)`
- **Card Radius**: `16px`
- **Card Shadow**: `var(--shadow-ref)`
- **User Avatar**: `40px` circle, `var(--ink-ref)` background, white text
- **User Email**: `0.8rem`, `var(--slate-2-ref)` color
- **Role Badges**: `var(--paper-2-ref)` background, `0.75rem` size
- **Status Pills**: Color-coded by status (active, inactive, etc.)
- **Button Styling**: Global button styles with size variants

### Navigation & Interactions
- **Create User**: Navigates to `/users/new`
- **User Name Link**: Navigates to `/users/{id}/edit`
- **Expand Toggle**: Shows/hides detailed user information
- **Edit User**: Navigates to edit page
- **Archive**: Triggers confirmation dialog and API call
- **Pagination**: Changes page with API call

### Data Displayed
- **User List**: Array of user objects from API
- **User Fields**: id, neon_auth_user_id, email, full_name, school_id, department_id, status, roles, mfa_enabled, phone, employee_id, created_at, archived_at
- **Pagination**: Current page, total count, page size (50)

---

## User Form — `/users/new` and `/users/:id/edit`

### Purpose
Create new user or edit existing user information with role assignment.

### Layout Structure
- Header with title and back button
- Centered form card
- Vertical form layout with grouped fields
- Checkbox group for role selection
- Action buttons at bottom

### Responsive behavior (CRITICAL — audit this carefully per screen)
- Does this screen currently have responsive/breakpoint logic? List exact breakpoints (px values) if defined in CSS/Tailwind config/media queries
- What changes at each breakpoint currently (columns collapse, sidebar hides, nav becomes hamburger, etc.)
- Flag anything that is CURRENTLY BROKEN or NOT HANDLED at smaller widths:
  - Tables/grids with many columns that have no mobile fallback
  - Fixed-width elements (px instead of %/rem/fr) that will overflow on small screens
  - Text or buttons that get cut off, truncated, or overlap at narrow widths
  - Modals/dropdowns/tooltips that may overflow viewport on mobile
  - Horizontal scroll present (intentional or accidental)
  - Touch target sizes (are buttons/links big enough for touch, or clearly mouse-only e.g. hover-only menus)
- Note the CSS framework/approach used for responsiveness (Tailwind breakpoints, CSS Grid, media queries, container queries, none)

Also add to the GLOBAL DESIGN SYSTEM section at the top:
- Full list of ALL breakpoints used anywhere in the app (px values)
- Whether the app uses a mobile-first or desktop-first CSS approach
- Any components that currently have ZERO responsive handling (will just break/overflow on small screens)

### Components on This Page
- **Page Header**: "Create User" or "Edit User" with back button
- **Back Button**: Secondary button linking to `/users`
- **Error Display**: Error message banner (if present)
- **Form Card**: Container for form fields
- **Neon Auth User ID Input**: Required text input (disabled on edit)
- **Email Input**: Required email input (disabled on edit)
- **Full Name Input**: Required text input
- **School ID Input**: Optional text input
- **Department ID Input**: Optional text input
- **Roles Checkbox Group**: Multiple checkboxes for role selection
- **Role Options**: SuperAdmin, Admin, Checker, Auditor, Viewer
- **Phone Input**: Optional phone input
- **Employee ID Input**: Optional text input
- **Cancel Button**: Secondary button to return to list
- **Submit Button**: Primary button with loading state

### Visual Styling
- **Form Card**: `var(--card-ref)` background, `1px solid var(--line-ref)` border, `16px` radius
- **Form Groups**: Standard spacing with labels above inputs
- **Label Styling**: `0.875rem`, weight 600, `var(--ink-ref)` color
- **Input Styling**: Full width, `0.75rem 1rem` padding, `1.5px solid var(--line-ref)` border, `10px` radius
- **Input Focus**: `var(--ink-ref)` border color with shadow
- **Input Disabled**: `var(--paper-2-ref)` background, not-allowed cursor
- **Checkbox Group**: Vertical layout with gap
- **Checkbox Labels**: Flex layout with gap, cursor pointer
- **Error Banner**: Gradient background with danger colors

### Navigation & Interactions
- **Back Button**: Navigates to `/users`
- **Cancel Button**: Navigates to `/users`
- **Submit Button**: Creates/updates user via API, then navigates to list
- **Role Toggles**: Add/remove roles from selection
- **Form Validation**: Requires at least one role selected
- **Loading State**: Button shows "Saving..." during API call

### Data Displayed
- **Form Data**: neon_auth_user_id, email, full_name, school_id, department_id, roles[], phone, employee_id
- **Edit Mode**: Pre-populated with existing user data
- **Create Mode**: Empty form with default values
- **Role Options**: Fixed list of available roles

---

## Dashboard — `/dashboard`

### Purpose
Main dashboard showing role-based overview with KPI, compliance, task, and discrepancy summaries.

### Layout Structure
- Page header with user context info
- Statistics ribbon with key metrics
- Collapsible sections for different data categories
- Grid layout for summary cards
- Table views for activities and pending actions

### Responsive behavior (CRITICAL — audit this carefully per screen)
- Does this screen currently have responsive/breakpoint logic? List exact breakpoints (px values) if defined in CSS/Tailwind config/media queries
- What changes at each breakpoint currently (columns collapse, sidebar hides, nav becomes hamburger, etc.)
- Flag anything that is CURRENTLY BROKEN or NOT HANDLED at smaller widths:
  - Tables/grids with many columns that have no mobile fallback
  - Fixed-width elements (px instead of %/rem/fr) that will overflow on small screens
  - Text or buttons that get cut off, truncated, or overlap at narrow widths
  - Modals/dropdowns/tooltips that may overflow viewport on mobile
  - Horizontal scroll present (intentional or accidental)
  - Touch target sizes (are buttons/links big enough for touch, or clearly mouse-only e.g. hover-only menus)
- Note the CSS framework/approach used for responsiveness (Tailwind breakpoints, CSS Grid, media queries, container queries, none)

Also add to the GLOBAL DESIGN SYSTEM section at the top:
- Full list of ALL breakpoints used anywhere in the app (px values)
- Whether the app uses a mobile-first or desktop-first CSS approach
- Any components that currently have ZERO responsive handling (will just break/overflow on small screens)

### Components on This Page
- **Page Header**: "Dashboard" heading with user context
- **Eyebrow**: "Dashboard" label with decorative dot
- **Context Info**: Role, school, department display
- **Statistics Ribbon**: Key metrics display (Open Tasks, Overdue, Completed, On Time Rate)
- **Collapsible Sections**: Expandable sections for different data categories
- **Summary Cards**: Metric cards with values and subtitles
- **KPI Summary Section**: Total KPIs, Not Met, Amber Status cards
- **Compliance Summary Section**: Total Due, Missed, Submission Rate cards
- **Discrepancy Summary Section**: Open Discrepancies, Pending Approval, SLA Breached cards
- **RAG Distribution Section**: Green, Amber, Red, Not Submitted clickable cards
- **Pending My Action Section**: Table of pending tasks
- **Recent Activities Section**: Table of recent system activities
- **Expand Icons**: ▶/▼ for section collapse/expand

### Visual Styling
- **Page Header**: `38px 40px 0` padding, flex layout
- **Eyebrow**: `11.5px`, uppercase, `var(--clay-ref)` color, decorative dot
- **Heading**: `38px`, `var(--font-display)`, weight 600
- **Context Text**: `14.5px`, `var(--slate-ref)` color
- **Ribbon**: `var(--ink-ref)` background, `16px` radius, gradient decoration
- **Ribbon Numbers**: `30px`, weight 600, white/gold/rose colors
- **Ribbon Labels**: `12.5px`, `#9FBFB8` color
- **Summary Cards**: `var(--card-ref)` background, `16px` radius, shadow
- **Card Values**: `2rem`, weight 700, color-coded by status
- **Card Subtitles**: `0.85rem`, `var(--slate-2-ref)` color
- **Clickable Cards**: Pointer cursor, hover lift effect
- **Table Headers**: Grid layout, uppercase, `11.5px`
- **Table Rows**: Grid layout, hover background change
- **Status Pills**: Color-coded by status

### Navigation & Interactions
- **RAG Cards**: Click to navigate to KPI verification with status filter
- **Section Toggle**: Expand/collapse sections with animation
- **Task Links**: Navigate to task details
- **Hover Effects**: Cards lift on hover, table rows highlight

### Data Displayed
- **User Context**: role, school_id, department_id
- **Task Summary**: open_tasks, overdue_tasks, completed_this_period, pct_on_time
- **KPI Summary**: total_kpis, met, not_met, amber, pct_met
- **Compliance Summary**: total_due, submitted, missed, late, pct_submitted
- **Discrepancy Summary**: open_discrepancies, under_investigation, pending_approval, resolved_this_period, breached_sla
- **RAG Distribution**: green, amber, red, not_submitted counts
- **Pending Actions**: task_id, title, status, eta
- **Recent Activities**: entity_type, entity_id, action, actor_name, timestamp

---

## Tasks — `/tasks`

### Purpose
Task management interface with filtering, search, and status tracking.

### Layout Structure
- Page header with eyebrow and description
- Statistics ribbon with task counts
- Controls bar with tabs and search
- Grid layout for task cards
- Empty state for no results

### Responsive behavior (CRITICAL — audit this carefully per screen)
- Does this screen currently have responsive/breakpoint logic? List exact breakpoints (px values) if defined in CSS/Tailwind config/media queries
- What changes at each breakpoint currently (columns collapse, sidebar hides, nav becomes hamburger, etc.)
- Flag anything that is CURRENTLY BROKEN or NOT HANDLED at smaller widths:
  - Tables/grids with many columns that have no mobile fallback
  - Fixed-width elements (px instead of %/rem/fr) that will overflow on small screens
  - Text or buttons that get cut off, truncated, or overlap at narrow widths
  - Modals/dropdowns/tooltips that may overflow viewport on mobile
  - Horizontal scroll present (intentional or accidental)
  - Touch target sizes (are buttons/links big enough for touch, or clearly mouse-only e.g. hover-only menus)
- Note the CSS framework/approach used for responsiveness (Tailwind breakpoints, CSS Grid, media queries, container queries, none)

Also add to the GLOBAL DESIGN SYSTEM section at the top:
- Full list of ALL breakpoints used anywhere in the app (px values)
- Whether the app uses a mobile-first or desktop-first CSS approach
- Any components that currently have ZERO responsive handling (will just break/overflow on small screens)

### Components on This Page
- **Page Header**: "Tasks" heading with description
- **Eyebrow**: "Task Management" label
- **Create Task Button**: Primary button with + icon
- **Statistics Ribbon**: Total tasks, Pending, In Progress, Completed counts
- **Controls Bar**: Tab navigation and search input
- **Tab Buttons**: All Tasks, Pending, In Progress, Completed with counts
- **Search Input**: Mini search with icon
- **Task Cards**: Floating cards with task information
- **Checkbox**: Visual completion indicator
- **Task Title**: Link to task details
- **Department Tag**: Styled department name
- **School Tag**: School identifier
- **Priority Indicator**: Dot with priority label (High/Medium/Low)
- **Due Date**: Formatted date with soon highlighting
- **Status Pill**: Color-coded status indicator
- **Expand Toggle**: Show/hide task details
- **Detail Sections**: Description, school ID, dates
- **View Details Button**: Link to task detail page
- **Edit Task Button**: Primary button for editing
- **Empty State**: Icon and message when no tasks found

### Visual Styling
- **Page Header**: Global `.page-head` styling
- **Ribbon**: Task-specific styling with count display
- **Tabs**: `var(--paper-2-ref)` background, rounded container
- **Tab Buttons**: Active state with `var(--card-ref)` background and shadow
- **Search Input**: `var(--card-ref)` background, `1px solid var(--line-ref)` border
- **Task Cards**: `var(--card-ref)` background, `1px solid var(--line-ref)` border, `16px` radius
- **Priority Dots**: `var(--rose-ref)` (high), `var(--gold-ref)` (medium), `var(--moss-ref)` (low)
- **Due Dates**: `var(--slate-ref)` color, `var(--rose-ref)` for soon dates
- **Status Pills**: `#F2E7D6` (pending), `#DCEAE6` (progress), `#E4EDE0` (completed)
- **Empty State**: Centered with icon and message

### Navigation & Interactions
- **Create Task**: Navigates to `/tasks/new`
- **Task Title Link**: Navigates to `/tasks/{id}`
- **Tab Navigation**: Filters task list by status
- **Search**: Real-time filtering by title and description
- **Expand Toggle**: Shows/hide task details
- **View Details**: Navigates to task detail page
- **Edit Task**: Navigates to `/tasks/{id}/edit`
- **Checkbox**: Visual indicator (no functionality)

### Data Displayed
- **Task List**: Array of task objects
- **Task Fields**: id, title, description, school_id, school_name, department_id, department_name, created_by, completion_rule, eta, eta_extension_count, status, priority, entity_type, entity_id, created_at, updated_at, completed_at, cancelled_at
- **Statistics**: Computed counts for each status
- **Priority Levels**: high, medium, low
- **Status Values**: open, in_progress, completed

---

## KRA List — `/kra`

### Purpose
Manage Key Result Areas and Key Performance Indicators with view toggles and filtering.

### Layout Structure
- Header with title, view toggle, search, and actions
- Loading skeleton during data fetch
- Grid layout for KRA cards or department cards
- Empty states for no results
- Error state with retry option

### Responsive behavior (CRITICAL — audit this carefully per screen)
- Does this screen currently have responsive/breakpoint logic? List exact breakpoints (px values) if defined in CSS/Tailwind config/media queries
- What changes at each breakpoint currently (columns collapse, sidebar hides, nav becomes hamburger, etc.)
- Flag anything that is CURRENTLY BROKEN or NOT HANDLED at smaller widths:
  - Tables/grids with many columns that have no mobile fallback
  - Fixed-width elements (px instead of %/rem/fr) that will overflow on small screens
  - Text or buttons that get cut off, truncated, or overlap at narrow widths
  - Modals/dropdowns/tooltips that may overflow viewport on mobile
  - Horizontal scroll present (intentional or accidental)
  - Touch target sizes (are buttons/links big enough for touch, or clearly mouse-only e.g. hover-only menus)
- Note the CSS framework/approach used for responsiveness (Tailwind breakpoints, CSS Grid, media queries, container queries, none)

Also add to the GLOBAL DESIGN SYSTEM section at the top:
- Full list of ALL breakpoints used anywhere in the app (px values)
- Whether the app uses a mobile-first or desktop-first CSS approach
- Any components that currently have ZERO responsive handling (will just break/overflow on small screens)

### Components on This Page
- **Page Header**: "Manage Key Result Areas and Key Performance Indicators"
- **View Toggle**: By Department / By KRA toggle buttons
- **Search Box**: Input with search icon
- **Deprecated Toggle**: Checkbox to include deprecated items
- **Create KRA Button**: Primary button with + icon
- **Loading Skeleton**: Card placeholders during loading
- **KRA Cards**: Expandable cards with KPI lists
- **Department Cards**: Cards grouping KPIs by department
- **KRA Expand Button**: ▶/▼ toggle for KPI expansion
- **KRA Name**: Display KRA name
- **KRA Description**: Display description (if present)
- **Status Badge**: Color-coded status indicator
- **KPI Count**: Number of KPIs in KRA
- **KPI Items**: Individual KPI entries with links
- **Immutable Badge**: Lock icon for immutable KPIs
- **Target Display**: Target value and unit
- **Frequency Display**: KPI frequency code
- **Edit KRA Button**: Ghost button for editing
- **Add KPI Button**: Accent button for adding KPIs
- **Deprecate KRA Button**: Danger button for deprecating
- **Empty State**: Icon and message for no results
- **Error State**: Error message with retry button

### Visual Styling
- **Header**: Flex layout with action buttons
- **View Toggle**: `#f3f4f6` background, `6px` radius, active state with white background
- **Search Box**: Relative positioning with icon, `250px` width
- **KRA Cards**: `#ffffff` background, `1px solid #e5e7eb` border, `8px` radius
- **Deprecated Cards**: `0.7` opacity, `#f9fafb` background
- **Department Cards**: Gradient header `linear-gradient(135deg, #e0e7ff 0%, #c7d2fe 100%)`
- **Status Badges**: `#dcfce7` (active), `#fef3c7` (deprecated)
- **KPI Items**: `#f9fafb` background, `1px solid #e5e7eb` border, `6px` radius
- **KPI Links**: `#3b82f6` color, hover underline
- **Button Variants**: Ghost, accent, danger styles
- **Loading Skeleton**: Shimmer animation on placeholder lines
- **Empty State**: Centered with emoji icon

### Navigation & Interactions
- **View Toggle**: Switches between KRA and department views
- **Search**: Real-time filtering by name/description
- **Deprecated Toggle**: Includes/excludes deprecated items
- **Create KRA**: Navigates to `/kra/new`
- **KRA Expand**: Shows/hides KPI list
- **KPI Links**: Navigates to `/kpi/{id}/edit`
- **Add KPI**: Navigates to `/kra/{id}/kpi/new`
- **Deprecate KRA**: Confirmation dialog and API call
- **Deprecate KPI**: Confirmation dialog and API call
- **Retry Button**: Re-fetches data on error

### Data Displayed
- **KRA List**: Array of KRA objects
- **KPI List**: Array of KPI objects grouped by KRA
- **KRA Fields**: id, name, description, status
- **KPI Fields**: kpi_id, kra_id, version, title, target_value, comparator, unit_of_measure, frequency_code, capture_type, status, is_immutable, category_code, suggested_department, is_sensitive, amber_tolerance_band
- **Department Grouping**: Inferred department from KPI titles/categories
- **Loading Stages**: 'kras', 'kpis', 'idle' with stage messages

---

## Daily KPI Input — `/kpi-entry`

### Purpose
Daily KPI data entry interface for department users to submit KPI values.

### Layout Structure
- Header with title, date picker, and actions
- Alert banners for success/error messages
- Grid layout for KPI input cards
- Bulk actions section
- Empty state for no assignments

### Responsive behavior (CRITICAL — audit this carefully per screen)
- Does this screen currently have responsive/breakpoint logic? List exact breakpoints (px values) if defined in CSS/Tailwind config/media queries
- What changes at each breakpoint currently (columns collapse, sidebar hides, nav becomes hamburger, etc.)
- Flag anything that is CURRENTLY BROKEN or NOT HANDLED at smaller widths:
  - Tables/grids with many columns that have no mobile fallback
  - Fixed-width elements (px instead of %/rem/fr) that will overflow on small screens
  - Text or buttons that get cut off, truncated, or overlap at narrow widths
  - Modals/dropdowns/tooltips that may overflow viewport on mobile
  - Horizontal scroll present (intentional or accidental)
  - Touch target sizes (are buttons/links big enough for touch, or clearly mouse-only e.g. hover-only menus)
- Note the CSS framework/approach used for responsiveness (Tailwind breakpoints, CSS Grid, media queries, container queries, none)

Also add to the GLOBAL DESIGN SYSTEM section at the top:
- Full list of ALL breakpoints used anywhere in the app (px values)
- Whether the app uses a mobile-first or desktop-first CSS approach
- Any components that currently have ZERO responsive handling (will just break/overflow on small screens)

### Components on This Page
- **Page Header**: "Daily KPI Data Entry" with description
- **Date Picker**: Date input with max date constraint
- **Clear Draft Button**: Secondary button to clear localStorage
- **Error Alert**: Alert banner with error message and close button
- **Success Alert**: Alert banner with success message and close button
- **KPI Input Cards**: Cards for each assigned KPI
- **KPI Title**: Display KPI name
- **KPI Meta**: Department and frequency information
- **Target Display**: Target value and unit
- **Input Groups**: Formatted input sections based on data type
- **Boolean Inputs**: Radio buttons for Yes/No values
- **Numeric Inputs**: Number input with step 0.01
- **Text Inputs**: Textarea for text values
- **Notes Textarea**: Optional notes field
- **Submit Button**: Primary button per KPI
- **Last Submission**: Display last submission date
- **Bulk Actions**: Centered section for bulk submission
- **Submit All Button**: Large primary button
- **Empty State**: Icon and message for no KPIs
- **Loading State**: Spinner with loading message

### Visual Styling
- **Header**: Flex layout with actions
- **Date Picker**: `1px solid #ddd` border, `6px` radius, white background
- **Alert Banners**: `#fef2f2` (error), `#f0fdf4` (success) backgrounds, `8px` radius
- **KPI Cards**: `#ffffff` background, `1px solid #e5e7eb` border, `8px` radius
- **Card Header**: Gradient background `linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%)`
- **Target Display**: White background, `1px solid #e5e7eb` border, `4px` radius
- **Input Fields**: `1px solid #d1d5db` border, `6px` radius, focus with `#3b82f6` border
- **Boolean Groups**: Horizontal radio layout with gap
- **Submit Button**: `#3b82f6` background, white text, `6px` radius
- **Empty State**: Centered with emoji icon
- **Loading Spinner**: `#3b82f6` border-top color, rotation animation

### Navigation & Interactions
- **Date Change**: Clears draft and reloads assignments
- **Clear Draft**: Removes localStorage draft and resets inputs
- **Alert Close**: Dismisses success/error messages
- **KPI Submit**: Validates and submits individual KPI via API
- **Submit All**: Bulk submission of all valid KPIs
- **Input Changes**: Auto-saves draft to localStorage
- **Draft Persistence**: Restores draft on page load
- **Loading State**: Shows spinner during data fetch

### Data Displayed
- **KPI Assignments**: Array of assigned KPIs for user's department
- **Assignment Fields**: id, kpi_id, kpi_title, kpi_target_value, kpi_unit, kpi_comparator, department_id, department_name, frequency_code, capture_type, data_type, version, last_submission_date
- **User Context**: Department ID, department name, school ID from session
- **Input Values**: Current input values from state or localStorage draft
- **Date Context**: Selected submission date

---

## KPI Verification — `/kpi-verification`

### Purpose
KPI verification dashboard for reviewing and approving/rejecting department submissions.

### Layout Structure
- Header with title, date picker, and actions
- Statistics cards grid
- Filters bar with dropdowns
- Observations list with expandable cards
- Bulk action bar for multi-select
- Modal dialogs for rejection/reopen requests
- Empty state for no observations

### Responsive behavior (CRITICAL — audit this carefully per screen)
- Does this screen currently have responsive/breakpoint logic? List exact breakpoints (px values) if defined in CSS/Tailwind config/media queries
- What changes at each breakpoint currently (columns collapse, sidebar hides, nav becomes hamburger, etc.)
- Flag anything that is CURRENTLY BROKEN or NOT HANDLED at smaller widths:
  - Tables/grids with many columns that have no mobile fallback
  - Fixed-width elements (px instead of %/rem/fr) that will overflow on small screens
  - Text or buttons that get cut off, truncated, or overlap at narrow widths
  - Modals/dropdowns/tooltips that may overflow viewport on mobile
  - Horizontal scroll present (intentional or accidental)
  - Touch target sizes (are buttons/links big enough for touch, or clearly mouse-only e.g. hover-only menus)
- Note the CSS framework/approach used for responsiveness (Tailwind breakpoints, CSS Grid, media queries, container queries, none)

Also add to the GLOBAL DESIGN SYSTEM section at the top:
- Full list of ALL breakpoints used anywhere in the app (px values)
- Whether the app uses a mobile-first or desktop-first CSS approach
- Any components that currently have ZERO responsive handling (will just break/overflow on small screens)

### Components on This Page
- **Page Header**: "KPI Verification Dashboard" with description
- **Date Picker**: Date input for filtering submissions
- **Statistics Cards**: Total Submissions, Pending Review, Verified, Late Submissions, Reopen Requests
- **Filters Bar**: Status, Department, RAG dropdowns
- **Filter Selects**: Custom styled select dropdowns
- **Bulk Action Bar**: Selection count and action buttons
- **Observation Cards**: Expandable cards with KPI data
- **Checkbox**: Multi-select checkbox
- **KPI Title**: Display KPI name
- **Department Badge**: Styled department name
- **Late Badge**: Red badge for late submissions
- **RAG Indicator**: Color-coded circle with status
- **Value Groups**: Target, actual, result display
- **Notes Section**: Background section for notes
- **Reopen Info**: Purple section for reopen requests
- **Status Badge**: Color-coded status indicator
- **Verify Button**: Primary blue button
- **Reject Button**: Secondary gray button
- **Reopen Request Button**: Button for requesting reopen
- **Approve Reopen Button**: Button for approving reopen
- **Deny Reopen Button**: Button for denying reopen
- **Reject Modal**: Modal with reason textarea
- **Reopen Modal**: Modal with reason textarea
- **Deny Reopen Modal**: Modal with reason textarea
- **Empty State**: Icon and message for no observations
- **Loading State**: Spinner with loading message

### Visual Styling
- **Header**: Flex layout with actions
- **Statistics Cards**: `#ffffff` background, `1px solid #e5e7eb` border, `8px` radius, colored icons
- **Filters Bar**: `#ffffff` background, `1px solid #e5e7eb` border, `8px` radius
- **Filter Selects**: `1px solid #d1d5db` border, `6px` radius, custom dropdown arrow
- **Observation Cards**: `#ffffff` background, `1px solid #e5e7eb` border, `8px` radius
- **Card Header**: Gradient background `linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%)`
- **RAG Indicator**: `3rem` circle, color-coded background
- **Status Badges**: `#f59e0b` (pending), `#22c55e` (verified), `#ef4444` (rejected)
- **Value Results**: `#059669` color for positive results
- **Buttons**: `#3b82f6` (primary), `#6b7280` (secondary), `#ef4444` (danger)
- **Modals**: Fixed overlay, centered content, `12px` radius
- **Empty State**: Centered with emoji icon
- **Loading Spinner**: `#3b82f6` border-top color, rotation animation

### Navigation & Interactions
- **Date Change**: Reloads observations for selected date
- **Filter Changes**: Updates observation list based on filters
- **Checkbox Selection**: Adds/removes from bulk selection set
- **Select All**: Toggles all pending observations
- **Card Expand**: Shows/hide detailed observation data
- **Verify**: Approves observation via API
- **Reject**: Opens rejection modal with reason input
- **Reopen Request**: Opens reopen modal with reason input
- **Approve Reopen**: Approves reopen request via API
- **Deny Reopen**: Opens deny modal with reason input
- **Bulk Verify**: Verifies all selected observations
- **Bulk Reject**: Opens rejection modal for bulk action
- **Modal Cancel**: Closes modal without action
- **Modal Submit**: Executes action with reason

### Data Displayed
- **Observations**: Array of observation objects from API
- **Observation Fields**: id, kpi_id, kpi_title, kpi_target_value, kpi_unit, kpi_comparator, department_name, checker_name, value_numeric, value_text, submission_date, rag_status, auto_result, status, is_late, verified_by, rejected_by, is_reopened, reopen_requested_at, reopen_requested_by, reopen_reason, reopen_approved_at, reopen_approved_by
- **Statistics**: Computed counts for total, pending, verified, late, reopen_requested
- **Filter Options**: Unique departments, status values, RAG values
- **User Context**: Current user ID for self-approval guards

---

## Reports — `/reports`

### Purpose
Report catalogue for accessing and generating system reports.

### Layout Structure
- Page header with eyebrow and description
- Grid layout for report cards
- Empty state for no reports

### Responsive behavior (CRITICAL — audit this carefully per screen)
- Does this screen currently have responsive/breakpoint logic? List exact breakpoints (px values) if defined in CSS/Tailwind config/media queries
- What changes at each breakpoint currently (columns collapse, sidebar hides, nav becomes hamburger, etc.)
- Flag anything that is CURRENTLY BROKEN or NOT HANDLED at smaller widths:
  - Tables/grids with many columns that have no mobile fallback
  - Fixed-width elements (px instead of %/rem/fr) that will overflow on small screens
  - Text or buttons that get cut off, truncated, or overlap at narrow widths
  - Modals/dropdowns/tooltips that may overflow viewport on mobile
  - Horizontal scroll present (intentional or accidental)
  - Touch target sizes (are buttons/links big enough for touch, or clearly mouse-only e.g. hover-only menus)
- Note the CSS framework/approach used for responsiveness (Tailwind breakpoints, CSS Grid, media queries, container queries, none)

Also add to the GLOBAL DESIGN SYSTEM section at the top:
- Full list of ALL breakpoints used anywhere in the app (px values)
- Whether the app uses a mobile-first or desktop-first CSS approach
- Any components that currently have ZERO responsive handling (will just break/overflow on small screens)

### Components on This Page
- **Page Header**: "Report Catalogue" with description
- **Eyebrow**: "Reports" label with decorative dot
- **Report Cards**: Individual cards for each report
- **Report Title**: Display report name
- **Report Description**: Display report description
- **Required Roles**: Badge list of required roles
- **Available Formats**: Badge list of export formats
- **Run Report Button**: Primary button linking to report runner
- **Empty State**: Icon and message for no reports
- **Loading State**: Loading message during fetch

### Visual Styling
- **Page Header**: Global `.page-head` styling
- **Report Cards**: `var(--card-ref)` background, `16px` radius, `1px solid var(--line-ref)` border
- **Report Title**: `var(--font-display)`, `18px`, weight 600
- **Report Description**: `var(--slate-ref)` color, `0.9rem`, `2.5rem` min-height
- **Role Badges**: `var(--paper-2-ref)` background, `4px` radius, `0.75rem` size
- **Format Badges**: `var(--moss-ref)` background, white text, `4px` radius
- **Run Button**: Full-width primary button
- **Empty State**: Centered with icon and message
- **Grid Layout**: `repeat(auto-fill, minmax(300px, 1fr))` with `1rem` gap

### Navigation & Interactions
- **Run Report**: Navigates to `/reports/{slug}` for report generation
- **Hover Effects**: Cards have shadow on hover (though not explicitly styled)

### Data Displayed
- **Reports**: Array of report objects from API
- **Report Fields**: slug, title, description, available_formats, required_roles
- **Format Display**: Uppercase format names (PDF, CSV, etc.)
- **Role Display**: Role names as badges

---

## Configuration — `/configuration`

### Purpose
Configuration management panel for system settings (note: this route appears to be replaced by the Settings page).

### Layout Structure
- Standard page layout with header
- Configuration sections
- Form-based configuration interface

### Responsive behavior (CRITICAL — audit this carefully per screen)
- Does this screen currently have responsive/breakpoint logic? List exact breakpoints (px values) if defined in CSS/Tailwind config/media queries
- What changes at each breakpoint currently (columns collapse, sidebar hides, nav becomes hamburger, etc.)
- Flag anything that is CURRENTLY BROKEN or NOT HANDLED at smaller widths:
  - Tables/grids with many columns that have no mobile fallback
  - Fixed-width elements (px instead of %/rem/fr) that will overflow on small screens
  - Text or buttons that get cut off, truncated, or overlap at narrow widths
  - Modals/dropdowns/tooltips that may overflow viewport on mobile
  - Horizontal scroll present (intentional or accidental)
  - Touch target sizes (are buttons/links big enough for touch, or clearly mouse-only e.g. hover-only menus)
- Note the CSS framework/approach used for responsiveness (Tailwind breakpoints, CSS Grid, media queries, container queries, none)

Also add to the GLOBAL DESIGN SYSTEM section at the top:
- Full list of ALL breakpoints used anywhere in the app (px values)
- Whether the app uses a mobile-first or desktop-first CSS approach
- Any components that currently have ZERO responsive handling (will just break/overflow on small screens)

### Components on This Page
- **Page Header**: Configuration title and actions
- **Config Sections**: Grouped configuration areas
- **Config Forms**: Form-based configuration inputs
- **Save Buttons**: Action buttons for saving configuration

### Visual Styling
- Uses global configuration styling from `module-components.css`
- Standard form and card styling
- Inherits global design tokens

### Navigation & Interactions
- Configuration save actions
- Section toggles (if applicable)

### Data Displayed
- System configuration values
- Settings from backend API

---

## Task Form — `/tasks/new` and `/tasks/:id/edit`

### Purpose
Create new task or edit existing task with owner assignment, school/department selection, and ETA scheduling.

### Layout Structure
- Header with title and back button
- Form card with grouped field sections
- Multi-owner selection with checkboxes
- Action buttons at bottom

### Responsive behavior (CRITICAL — audit this carefully per screen)
- Does this screen currently have responsive/breakpoint logic? List exact breakpoints (px values) if defined in CSS/Tailwind config/media queries
- What changes at each breakpoint currently (columns collapse, sidebar hides, nav becomes hamburger, etc.)
- Flag anything that is CURRENTLY BROKEN or NOT HANDLED at smaller widths:
  - Tables/grids with many columns that have no mobile fallback
  - Fixed-width elements (px instead of %/rem/fr) that will overflow on small screens
  - Text or buttons that get cut off, truncated, or overlap at narrow widths
  - Modals/dropdowns/tooltips that may overflow viewport on mobile
  - Horizontal scroll present (intentional or accidental)
  - Touch target sizes (are buttons/links big enough for touch, or clearly mouse-only e.g. hover-only menus)
- Note the CSS framework/approach used for responsiveness (Tailwind breakpoints, CSS Grid, media queries, container queries, none)

Also add to the GLOBAL DESIGN SYSTEM section at the top:
- Full list of ALL breakpoints used anywhere in the app (px values)
- Whether the app uses a mobile-first or desktop-first CSS approach
- Any components that currently have ZERO responsive handling (will just break/overflow on small screens)

### Components on This Page
- **Page Header**: "Create Task" or "Edit Task" with back button
- **Back Button**: Secondary button linking to `/tasks`
- **Form Card**: Container for task fields
- **Title Input**: Required text input (max 255 characters)
- **Description Textarea**: Optional task description (3 rows)
- **School Select**: Required dropdown for school selection (populated from API)
- **Department Select**: Optional dropdown for department selection (populated based on school)
- **Completion Rule Select**: Required dropdown (Any Owner, All Owners, Majority of Owners)
- **ETA Input**: Required datetime-local input for due date
- **Task Owners Section**: Checkbox group for multi-owner selection
- **Owner Checkboxes**: Vertical list of users with checkboxes
- **Entity Type Input**: Optional text input for related entity type
- **Entity ID Input**: Optional text input for related entity ID
- **Cancel Button**: Secondary button to return to list
- **Submit Button**: Primary button with loading state

### Visual Styling
- **Header**: Uses global `.header` class with bottom border
- **Form Card**: `var(--card-ref)` background, `1px solid var(--line-ref)` border, `16px` radius, `var(--shadow-ref)` shadow
- **Form Groups**: Standard spacing with labels above inputs
- **Form Row**: Grid layout for paired inputs
- **Label Styling**: `0.875rem`, weight 600, `var(--ink-ref)` color
- **Input Styling**: Full width, `0.75rem 1rem` padding, `1.5px solid var(--line-ref)` border, `10px` radius
- **Input Focus**: `var(--ink-ref)` border color with shadow
- **Select Styling**: Same as input styling
- **Checkbox Group**: Vertical layout with gap
- **Checkbox Labels**: Flex layout with gap, cursor pointer
- **Button Styling**: Global button styles with variants (primary, secondary)

### Navigation & Interactions
- **Back Button**: Navigates to `/tasks`
- **School Selection**: Triggers department population via API, clears department selection
- **Owner Toggles**: Add/remove users from owner_ids array
- **Form Submit**: Creates/updates task via API, then navigates to list
- **Form Validation**: HTML5 required validation + API validation
- **Loading State**: Button shows "Saving…" during API call
- **Edit Mode Restriction**: completion_rule excluded from PATCH requests (immutable)
- **Department Dependency**: Department dropdown disabled until school is selected

### Data Displayed
- **Form Data**: title, description, owner_ids (array), completion_rule, eta, school_id, department_id, entity_type, entity_id
- **Schools List**: Array of school objects from API (up to 100)
- **Departments List**: Array of department objects filtered by school_id (up to 100)
- **Users List**: Array of user objects from API (up to 100)
- **Edit Mode**: Pre-populated with existing task data (completion_rule not editable)
- **Create Mode**: Empty form with default values (any_owner completion rule)
- **User Context**: Current user ID from localStorage for created_by

---

## Task Detail — `/tasks/:id`

### Purpose
Detailed view of individual task with status display, completion action, and ETA extension request functionality.

### Layout Structure
- Header with title and back button
- Form card displaying task information as read-only fields
- Action buttons based on task status
- Inline form for ETA extension requests

### Responsive behavior (CRITICAL — audit this carefully per screen)
- Does this screen currently have responsive/breakpoint logic? List exact breakpoints (px values) if defined in CSS/Tailwind config/media queries
- What changes at each breakpoint currently (columns collapse, sidebar hides, nav becomes hamburger, etc.)
- Flag anything that is CURRENTLY BROKEN or NOT HANDLED at smaller widths:
  - Tables/grids with many columns that have no mobile fallback
  - Fixed-width elements (px instead of %/rem/fr) that will overflow on small screens
  - Text or buttons that get cut off, truncated, or overlap at narrow widths
  - Modals/dropdowns/tooltips that may overflow viewport on mobile
  - Horizontal scroll present (intentional or accidental)
  - Touch target sizes (are buttons/links big enough for touch, or clearly mouse-only e.g. hover-only menus)
- Note the CSS framework/approach used for responsiveness (Tailwind breakpoints, CSS Grid, media queries, container queries, none)

Also add to the GLOBAL DESIGN SYSTEM section at the top:
- Full list of ALL breakpoints used anywhere in the app (px values)
- Whether the app uses a mobile-first or desktop-first CSS approach
- Any components that currently have ZERO responsive handling (will just break/overflow on small screens)

### Components on This Page
- **Page Header**: "Task Details" with back button
- **Back Button**: Secondary button linking to `/tasks`
- **Form Card**: Container for task information display
- **Title Display**: Read-only display of task title
- **Description Display**: Read-only display of task description (if present)
- **Status Badge**: Color-coded status indicator
- **Completion Rule Display**: Display of completion rule
- **ETA Display**: Formatted date/time string
- **ETA Extensions Display**: Count of extension requests
- **Created/Updated Dates**: Formatted date/time strings
- **Completed At Display**: Formatted date/time (if present)
- **Entity Type/ID Display**: Related entity information (if present)
- **Complete Task Button**: Primary button (shown when status is pending or in_progress)
- **Request ETA Extension Button**: Accent button (shown when task is not completed or cancelled)
- **Edit Task Button**: Secondary button linking to edit form
- **ETA Extension Form**: Inline form for extension requests
- **New ETA Input**: Required datetime-local input
- **Justification Textarea**: Optional textarea for extension reason
- **Extension Cancel Button**: Secondary button to cancel form
- **Extension Submit Button**: Primary button with loading state

### Visual Styling
- **Header**: Uses global `.header` class with bottom border
- **Form Card**: `var(--card-ref)` background, `1px solid var(--line-ref)` border, `16px` radius, `var(--shadow-ref)` shadow
- **Form Groups**: Standard spacing with labels above values
- **Form Row**: Grid layout for paired information display
- **Status Badges**: Color-coded by status using global `.status` classes
- **Inline Form**: Same styling as main form card, nested with margin
- **Form Heading**: `var(--font-display)` font family, `var(--ink-ref)` color
- **Button Styling**: Global button styles with variants (primary, accent, secondary)
- **Conditional Button Display**: Based on task status logic

### Navigation & Interactions
- **Back Button**: Returns to task list
- **Complete Task**: Triggers confirmation dialog, marks task as complete via API
- **Request ETA Extension**: Toggles inline form visibility
- **ETA Extension Submit**: Submits extension request with new ETA and justification via API
- **Form Cancellation**: Hides inline form, resets form data
- **Edit Task**: Navigates to `/tasks/{id}/edit`
- **Status-Based Actions**: Buttons shown/hidden based on current task status

### Data Displayed
- **Task Object**: Full task details from API
- **Task Fields**: id, title, description, school_id, department_id, created_by, completion_rule, eta, eta_extension_count, status, entity_type, entity_id, created_at, updated_at, completed_at, cancelled_at
- **Status Logic**: canComplete (status='pending' or 'in_progress'), canExtend (status not 'completed' or 'cancelled')
- **User Context**: Current user ID from localStorage for completion and extension actions

---

## Escalation Rules — `/escalation-rules`

### Purpose
Manage task escalation rules with SLA configuration, school/department scope, and role-based escalation targets.

### Layout Structure
- Header with title and add rule toggle button
- Create/edit form for escalation rules
- Table display of existing rules
- Info banner explaining escalation workflow

### Responsive behavior (CRITICAL — audit this carefully per screen)
- Does this screen currently have responsive/breakpoint logic? List exact breakpoints (px values) if defined in CSS/Tailwind config/media queries
- What changes at each breakpoint currently (columns collapse, sidebar hides, nav becomes hamburger, etc.)
- Flag anything that is CURRENTLY BROKEN or NOT HANDLED at smaller widths:
  - Tables/grids with many columns that have no mobile fallback
  - Fixed-width elements (px instead of %/rem/fr) that will overflow on small screens
  - Text or buttons that get cut off, truncated, or overlap at narrow widths
  - Modals/dropdowns/tooltips that may overflow viewport on mobile
  - Horizontal scroll present (intentional or accidental)
  - Touch target sizes (are buttons/links big enough for touch, or clearly mouse-only e.g. hover-only menus)
- Note the CSS framework/approach used for responsiveness (Tailwind breakpoints, CSS Grid, media queries, container queries, none)

Also add to the GLOBAL DESIGN SYSTEM section at the top:
- Full list of ALL breakpoints used anywhere in the app (px values)
- Whether the app uses a mobile-first or desktop-first CSS approach
- Any components that currently have ZERO responsive handling (will just break/overflow on small screens)

### Components on This Page
- **Page Header**: "Escalation Rules" with add rule toggle button
- **Add Rule Button**: Primary button, toggles between "Add Rule" and "Cancel"
- **Create Rule Form**: Config form for creating new escalation rules
- **Escalation Level Input**: Required number input (min 1)
- **SLA Hours Input**: Required number input for SLA in hours (min 1, default 24)
- **School Select**: Dropdown for school selection (optional, "All Schools" default)
- **Department Select**: Dropdown for department selection (optional, "All Departments" default, disabled until school selected)
- **Escalate To Role ID Input**: Optional text input for role UUID
- **Save Rule Button**: Primary button with loading state
- **Cancel Button**: Secondary button to cancel form
- **Rules Table**: Data table displaying existing rules
- **Level Column**: Escalation level number
- **SLA Column**: SLA hours with "h" suffix
- **School Column**: "Specific" or "All Schools"
- **Department Column**: "Specific" or "All Departments"
- **Escalate To Role Column**: Role ID or "Default"
- **Created Column**: Formatted date string
- **Empty State**: "No escalation rules configured" message
- **Info Banner**: Yellow gradient banner explaining escalation workflow

### Visual Styling
- **Header**: Uses global `.header` class with bottom border
- **Config Form**: `var(--card-ref)` background, `1px solid var(--line-ref)` border, `16px` radius, `var(--shadow-ref)` shadow
- **Form Groups**: Standard spacing with labels above inputs
- **Form Row**: Grid layout for paired inputs
- **Label Styling**: Standard form label styling
- **Input Styling**: Full width, standard border and focus states
- **Select Styling**: Same as input styling
- **Table Styling**: Global `.data-table` and `.table-wrap` classes
- **Button Styling**: Global button styles with variants (primary, secondary)
- **Info Banner**: `linear-gradient(135deg, #FEF9C3, #FDE68A)` background, `#FCD34D` border, `#713F12` color
- **Empty State**: Global `.empty-state` styling

### Navigation & Interactions
- **Add Rule Toggle**: Shows/hides inline form, resets form data
- **School Selection**: Triggers department population via API, clears department selection
- **Form Submit**: Creates new escalation rule via API, refreshes rules list
- **Form Cancellation**: Hides form, resets form data
- **Department Dependency**: Department dropdown disabled until school is selected

### Data Displayed
- **Escalation Rules**: Array of rule objects from API
- **Rule Fields**: id, escalation_level, sla_hours, school_id, department_id, escalate_to_role_id, created_at, updated_at
- **Schools List**: Array of school objects from API (up to 100)
- **Departments List**: Array of department objects filtered by school_id (up to 100)
- **Form Data**: escalation_level (default 1), sla_hours (default 24), school_id, department_id, escalate_to_role_id
- **Escalation Logic**: Tasks exceeding ETA trigger automatic escalation; after 4 extensions, task escalates per R-33/BR-10

---

## Report Runner — `/reports/:reportType`

### Purpose
Generate and run specific reports with filter parameters, pagination, and export functionality.

### Layout Structure
- Header with report title and export controls
- Filter configuration form
- Results table with pagination
- Export format selection

### Responsive behavior (CRITICAL — audit this carefully per screen)
- Does this screen currently have responsive/breakpoint logic? List exact breakpoints (px values) if defined in CSS/Tailwind config/media queries
- What changes at each breakpoint currently (columns collapse, sidebar hides, nav becomes hamburger, etc.)
- Flag anything that is CURRENTLY BROKEN or NOT HANDLED at smaller widths:
  - Tables/grids with many columns that have no mobile fallback
  - Fixed-width elements (px instead of %/rem/fr) that will overflow on small screens
  - Text or buttons that get cut off, truncated, or overlap at narrow widths
  - Modals/dropdowns/tooltips that may overflow viewport on mobile
  - Horizontal scroll present (intentional or accidental)
  - Touch target sizes (are buttons/links big enough for touch, or clearly mouse-only e.g. hover-only menus)
- Note the CSS framework/approach used for responsiveness (Tailwind breakpoints, CSS Grid, media queries, container queries, none)

Also add to the GLOBAL DESIGN SYSTEM section at the top:
- Full list of ALL breakpoints used anywhere in the app (px values)
- Whether the app uses a mobile-first or desktop-first CSS approach
- Any components that currently have ZERO responsive handling (will just break/overflow on small screens)

### Components on This Page
- **Page Header**: Report title (uppercase, underscore replaced with spaces)
- **Export Format Select**: Dropdown for CSV, Excel, PDF selection
- **Export Button**: Primary button with loading state
- **Filter Form**: Config form with filter inputs
- **Date From Input**: Date input for start date filter
- **Date To Input**: Date input for end date filter
- **Status Input**: Text input for status filter (e.g., active, pending)
- **Apply Filters Button**: Primary button to refresh report
- **Clear Filters Button**: Secondary button to reset all filters
- **Results Table**: Data table with dynamic columns
- **Table Headers**: Column names converted to uppercase, underscores replaced with spaces
- **Table Rows**: Formatted cell values from report data
- **Pagination Controls**: Previous/Next buttons with page indicator
- **Total Records Display**: Text showing total row count
- **Empty State**: "No data available" message

### Visual Styling
- **Header**: Uses global `.header` class with bottom border
- **Export Controls**: Flex layout with gap, select styled as button
- **Config Form**: `var(--card-ref)` background, `1px solid var(--line-ref)` border, `16px` radius, `var(--shadow-ref)` shadow
- **Form Groups**: Standard spacing with labels above inputs
- **Form Row**: Grid layout for paired filter inputs
- **Button Styling**: Global button styles with variants (primary, secondary, small)
- **Table Styling**: Global `.data-table` and `.table-wrap` classes
- **Pagination**: Global `.pagination` styling
- **Empty State**: Global `.empty-state` styling
- **Cell Formatting**: Helper function formats null, boolean, and date values

### Navigation & Interactions
- **Export**: Queues export job via API, shows job ID in alert
- **Format Selection**: Changes export format (CSV, Excel, PDF)
- **Filter Changes**: Updates filter state, triggers report refresh
- **Apply Filters**: Fetches report with current filters
- **Clear Filters**: Resets all filters to empty strings
- **Pagination**: Changes page number, triggers report refresh
- **Back**: No back button - user must navigate manually

### Data Displayed
- **Report Data**: Object containing report_type, generated_at, total_rows, page, page_size, has_next, columns (array), rows (array of objects)
- **Filter State**: date_from, date_to, school_id, department_id, status
- **Pagination State**: Current page, page size (100), total rows, has_next flag
- **Export Format**: csv, excel, pdf (default: excel)
- **Cell Values**: Formatted as strings (null/undefined → '-', boolean → Yes/No, dates → locale string)

---

## Global Search — `/search`

### Purpose
Global search interface for finding entities across the system with faceted filtering and pagination.

### Layout Structure
- Header with title
- Search form with main input and filter options
- Results display with entity-specific cards
- Load more functionality for pagination
- Empty state for no results

### Responsive behavior (CRITICAL — audit this carefully per screen)
- Does this screen currently have responsive/breakpoint logic? List exact breakpoints (px values) if defined in CSS/Tailwind config/media queries
- What changes at each breakpoint currently (columns collapse, sidebar hides, nav becomes hamburger, etc.)
- Flag anything that is CURRENTLY BROKEN or NOT HANDLED at smaller widths:
  - Tables/grids with many columns that have no mobile fallback
  - Fixed-width elements (px instead of %/rem/fr) that will overflow on small screens
  - Text or buttons that get cut off, truncated, or overlap at narrow widths
  - Modals/dropdowns/tooltips that may overflow viewport on mobile
  - Horizontal scroll present (intentional or accidental)
  - Touch target sizes (are buttons/links big enough for touch, or clearly mouse-only e.g. hover-only menus)
- Note the CSS framework/approach used for responsiveness (Tailwind breakpoints, CSS Grid, media queries, container queries, none)

Also add to the GLOBAL DESIGN SYSTEM section at the top:
- Full list of ALL breakpoints used anywhere in the app (px values)
- Whether the app uses a mobile-first or desktop-first CSS approach
- Any components that currently have ZERO responsive handling (will just break/overflow on small screens)

### Components on This Page
- **Page Header**: "Global Search" heading
- **Search Form**: Form with main search input and filters
- **Search Input Wrapper**: Container for main search input and submit button
- **Search Input**: Large text input with placeholder "Search across all entities..."
- **Search Submit Button**: Button with loading spinner (⏳) or search icon (🔍)
- **Search Filters**: Filter options section
- **Entity Types Input**: Text input for entity type filtering (e.g., task,observation,user)
- **Date From Input**: Date input for start date filter
- **Date To Input**: Date input for end date filter
- **Clear Button**: Button to reset all filters and results
- **Results Header**: Shows result count and "Showing X of Y" text
- **Empty State**: "No results found for {query}" message
- **Search Result Cards**: Individual result cards with entity-specific styling
- **Entity Icon**: Emoji icon based on entity type (📋, 👁️, 👤, 🏫, 📁, 🎯, 📊)
- **Entity Type Badge**: Uppercase badge showing entity type
- **Relevance Score**: Percentage match display (if available)
- **Result Title**: Bold display of result title
- **Result Description**: Optional description text
- **Result Metadata**: ID and creation date display
- **Load More Button**: Primary button for pagination

### Visual Styling
- **Header**: Uses global `.header` class with bottom border
- **Search Form**: Uses global `.search-form` styling from index.css
- **Search Input**: `14px` font, `2px solid var(--line-ref)` border, `12px` radius, focus with `var(--gold-ref)` border and shadow
- **Search Submit Button**: `50px` square button, `var(--ink-ref)` background, hover scale effect
- **Filter Inputs**: `1px solid var(--line-ref)` border, `8px` radius, focus with `var(--gold-ref)` border
- **Filter Labels**: `12px`, uppercase, `var(--slate-2-ref)` color
- **Clear Button**: `1px solid var(--line-ref)` border, `var(--paper-2-ref)` background, `40px` height
- **Result Cards**: `var(--card-ref)` background, `1px solid var(--line-ref)` border, `16px` radius, flex layout
- **Entity Icon**: `40px` square, `var(--bg-deep)` background, `8px` radius, centered emoji
- **Entity Type Badge**: `var(--bg-deep)` background, `4px` radius, `0.75rem` size, uppercase
- **Relevance Score**: `var(--text-muted)` color, percentage display
- **Result Title**: Weight 600, `var(--ink-ref)` color
- **Result Description**: `0.875rem`, `var(--text-muted)` color
- **Result Metadata**: `0.75rem`, `var(--text-muted)` color
- **Load More Button**: Centered primary button with loading state

### Navigation & Interactions
- **Search Submit**: Triggers search with current query and filters
- **Filter Changes**: Updates filter state, resets to page 1
- **Clear Button**: Resets all filters, results, and search state
- **Load More**: Fetches next page of results, appends to existing results
- **Result Card Click**: Currently no navigation (display only)

### Data Displayed
- **Search Results**: Array of result objects from API
- **Result Fields**: entity_type, entity_id, title, description, school_id, department_id, created_at, relevance_score
- **Pagination**: Current page, page size (20), total count, has_next
- **Filter State**: entity_types, school_id, department_id, date_from, date_to
- **Entity Types**: task, observation, user, school, department, kra, kpi
- **Entity Icons**: Mapped emoji icons per entity type

---

## Discrepancy List — `/discrepancies`

### Purpose
List view of audit discrepancies with state-based filtering and management actions.

### Layout Structure
- Header with title and "Raise Discrepancy" button
- Tab-based filtering by discrepancy state
- Table layout for discrepancy list
- Empty state for no results

### Responsive behavior (CRITICAL — audit this carefully per screen)
- Does this screen currently have responsive/breakpoint logic? List exact breakpoints (px values) if defined in CSS/Tailwind config/media queries
- What changes at each breakpoint currently (columns collapse, sidebar hides, nav becomes hamburger, etc.)
- Flag anything that is CURRENTLY BROKEN or NOT HANDLED at smaller widths:
  - Tables/grids with many columns that have no mobile fallback
  - Fixed-width elements (px instead of %/rem/fr) that will overflow on small screens
  - Text or buttons that get cut off, truncated, or overlap at narrow widths
  - Modals/dropdowns/tooltips that may overflow viewport on mobile
  - Horizontal scroll present (intentional or accidental)
  - Touch target sizes (are buttons/links big enough for touch, or clearly mouse-only e.g. hover-only menus)
- Note the CSS framework/approach used for responsiveness (Tailwind breakpoints, CSS Grid, media queries, container queries, none)

Also add to the GLOBAL DESIGN SYSTEM section at the top:
- Full list of ALL breakpoints used anywhere in the app (px values)
- Whether the app uses a mobile-first or desktop-first CSS approach
- Any components that currently have ZERO responsive handling (will just break/overflow on small screens)

### Components on This Page
- **Page Header**: "Audit Discrepancies" heading with create button
- **Raise Discrepancy Button**: Primary button linking to `/discrepancies/new`
- **State Tabs**: All, Raised, Under Investigation, Resolved, Pending Approval, Approved, Closed tabs
- **Table Container**: Wrapped table with overflow handling
- **Data Table**: Standard table with headers and rows
- **ID Column**: Truncated discrepancy ID with link to detail
- **State Column**: Color-coded status badge
- **Observation ID Column**: Truncated observation ID
- **Raised By Column**: Truncated user ID
- **Investigation Owner Column**: Truncated owner ID or dash
- **Raised At Column**: Formatted date string
- **View Button**: Small button linking to detail page
- **Empty State**: "No discrepancies found" message

### Visual Styling
- **Header**: Uses global `.header` class with bottom border
- **Tabs**: `var(--paper-2-ref)` background, rounded container, active state with `var(--card-ref)` background
- **Table Container**: `var(--card-ref)` background, `1px solid var(--line-ref)` border, `16px` radius
- **Table Headers**: `var(--paper-ref)` background, uppercase text, `0.78rem` size
- **Status Badges**: Color-coded by state (raised, under_investigation, resolved, pending_approval, approved, closed)
- **Link Styling**: `var(--ink-ref)` color, no decoration
- **Button Styling**: Global button styles with small variant

### Navigation & Interactions
- **Raise Discrepancy**: Navigates to `/discrepancies/new`
- **State Tabs**: Filters discrepancy list by state
- **ID Link**: Navigates to `/discrepancies/{id}`
- **View Button**: Navigates to discrepancy detail page
- **Table Hover**: Row background changes on hover

### Data Displayed
- **Discrepancy List**: Array of discrepancy objects from API
- **Discrepancy Fields**: id, observation_id, category_id, school_id, department_id, raised_by_user_id, investigation_owner_id, state, investigation_findings, bound_chain_version_id, raised_at, under_investigation_at, resolved_at, closed_at, created_at, updated_at
- **State Values**: raised, under_investigation, resolved, pending_approval, approved, closed

---

## Discrepancy Detail — `/discrepancies/:id`

### Purpose
Detailed view of individual discrepancy with investigation assignment, findings submission, and approval workflow management.

### Layout Structure
- Header with title and back button
- Config form card with discrepancy information display
- Form-based action sections for investigation assignment and findings
- Conditional action buttons based on discrepancy state
- Inline forms for assignee selection and findings submission

### Responsive behavior (CRITICAL — audit this carefully per screen)
- Does this screen currently have responsive/breakpoint logic? List exact breakpoints (px values) if defined in CSS/Tailwind config/media queries
- What changes at each breakpoint currently (columns collapse, sidebar hides, nav becomes hamburger, etc.)
- Flag anything that is CURRENTLY BROKEN or NOT HANDLED at smaller widths:
  - Tables/grids with many columns that have no mobile fallback
  - Fixed-width elements (px instead of %/rem/fr) that will overflow on small screens
  - Text or buttons that get cut off, truncated, or overlap at narrow widths
  - Modals/dropdowns/tooltips that may overflow viewport on mobile
  - Horizontal scroll present (intentional or accidental)
  - Touch target sizes (are buttons/links big enough for touch, or clearly mouse-only e.g. hover-only menus)
- Note the CSS framework/approach used for responsiveness (Tailwind breakpoints, CSS Grid, media queries, container queries, none)

Also add to the GLOBAL DESIGN SYSTEM section at the top:
- Full list of ALL breakpoints used anywhere in the app (px values)
- Whether the app uses a mobile-first or desktop-first CSS approach
- Any components that currently have ZERO responsive handling (will just break/overflow on small screens)

### Components on This Page
- **Page Header**: "Discrepancy Details" with back button
- **Back Button**: Secondary button linking to `/discrepancies`
- **Config Form**: Container for discrepancy information
- **State Display**: Color-coded status badge (state.replace(/_/g, ' '))
- **Discrepancy ID**: Full UUID display
- **Observation ID**: Full UUID display
- **Category ID**: Full UUID display
- **School ID**: Full UUID display
- **Department ID**: UUID display or "N/A"
- **Raised By**: User UUID display
- **Investigation Owner**: User UUID or "Not assigned"
- **Investigation Findings**: Pre-formatted text in styled box
- **Timeline Dates**: Formatted date strings for raised_at, under_investigation_at, resolved_at, closed_at
- **Assign Investigation Button**: Primary button (shown when state = 'raised')
- **Submit Findings Button**: Primary button (shown when state = 'under_investigation')
- **Start Approval Button**: Accent button (shown when state = 'resolved')
- **Approve Button**: Success button (shown when state starts with 'pending_approval')
- **Assign Investigation Form**: Inline form with user ID input
- **Findings Form**: Inline form with textarea for investigation findings
- **Cancel Buttons**: Secondary buttons for form cancellation

### Visual Styling
- **Header**: Uses global `.header` class with bottom border
- **Config Form**: `var(--card-ref)` background, `1px solid var(--line-ref)` border, `16px` radius, `var(--shadow-ref)` shadow
- **Form Groups**: Standard spacing with labels above values
- **Status Badges**: Color-coded by state using global `.status` classes
- **Investigation Findings Box**: `var(--bg-deep)` background, `var(--radius-sm)` radius, pre-wrap text
- **Form Rows**: Grid layout for paired information display
- **Inline Forms**: Same styling as main config form, nested with margin
- **Button Styling**: Global button styles with variants (primary, accent, success, danger)
- **Conditional Button Display**: Based on discrepancy state logic

### Navigation & Interactions
- **Back Button**: Returns to discrepancy list
- **Assign Investigation**: Opens inline form, assigns investigation_owner_id via API
- **Submit Findings**: Opens inline form, submits investigation_findings via API
- **Start Approval**: Triggers approval workflow via API
- **Approve**: Prompts for approval level, submits approval via API
- **Form Cancellation**: Closes inline forms without saving
- **State-Based Actions**: Buttons shown/hidden based on current discrepancy state

### Data Displayed
- **Discrepancy Object**: Full discrepancy details from API
- **Discrepancy Fields**: id, observation_id, category_id, school_id, department_id, raised_by_user_id, investigation_owner_id, state, investigation_findings, bound_chain_version_id, raised_at, under_investigation_at, resolved_at, closed_at, created_at, updated_at
- **State Logic**: canAssign (state='raised'), canSubmitFindings (state='under_investigation'), canStartApproval (state='resolved'), canApprove (state starts with 'pending_approval')
- **User Context**: Current user ID from localStorage for approval actions

---

## Approval Chains — `/approval-chains`

### Purpose
Manage approval chain configurations for discrepancy approval workflows with multi-level approval setup.

### Layout Structure
- Header with title and create button
- Active chain display with special highlighting
- Create/edit form for new approval chains
- Level configuration with role assignment
- Inactive chains list with activation option

### Responsive behavior (CRITICAL — audit this carefully per screen)
- Does this screen currently have responsive/breakpoint logic? List exact breakpoints (px values) if defined in CSS/Tailwind config/media queries
- What changes at each breakpoint currently (columns collapse, sidebar hides, nav becomes hamburger, etc.)
- Flag anything that is CURRENTLY BROKEN or NOT HANDLED at smaller widths:
  - Tables/grids with many columns that have no mobile fallback
  - Fixed-width elements (px instead of %/rem/fr) that will overflow on small screens
  - Text or buttons that get cut off, truncated, or overlap at narrow widths
  - Modals/dropdowns/tooltips that may overflow viewport on mobile
  - Horizontal scroll present (intentional or accidental)
  - Touch target sizes (are buttons/links big enough for touch, or clearly mouse-only e.g. hover-only menus)
- Note the CSS framework/approach used for responsiveness (Tailwind breakpoints, CSS Grid, media queries, container queries, none)

Also add to the GLOBAL DESIGN SYSTEM section at the top:
- Full list of ALL breakpoints used anywhere in the app (px values)
- Whether the app uses a mobile-first or desktop-first CSS approach
- Any components that currently have ZERO responsive handling (will just break/overflow on small screens)

### Components on This Page
- **Page Header**: "Approval Chains" with create/new chain toggle button
- **Create New Chain Button**: Primary button, toggles form visibility
- **Active Chain Card**: Highlighted card with green border showing current active chain
- **Active Status Badge**: Green "Active" status indicator
- **Active Chain Levels**: Nested table showing approval levels
- **Chain Creation Form**: Form for creating new approval chains
- **Approval Levels Section**: Dynamic level management
- **Add Level Button**: Small button to add additional approval levels
- **Level Cards**: Individual level configuration cards
- **Level Number**: Display of level number (1, 2, 3, etc.)
- **Remove Level Button**: Danger button to remove level (disabled for single level)
- **Role ID Input**: Required text input for role UUID assignment
- **Auto-escalation SLA Input**: Number input for hours (default 24)
- **Cancel Button**: Secondary button to cancel form
- **Create Chain Button**: Primary button with loading state
- **All Chains Header**: Section header for inactive chains
- **Inactive Chain Cards**: Cards for inactive approval chains
- **Chain ID Display**: Truncated chain version ID
- **Inactive Status Badge**: "Inactive" status indicator
- **Activate Button**: Primary button to activate chain
- **Chain Levels Table**: Nested table showing level configuration
- **Empty State**: "No approval chains configured" message

### Visual Styling
- **Header**: Uses global `.header` class with bottom border
- **Active Chain Card**: `2px solid var(--moss-ref)` border for emphasis
- **Active Status**: Green color using `var(--moss-ref)` with status badge styling
- **Form Cards**: `var(--card-ref)` background, `1px solid var(--line-ref)` border, `16px` radius
- **Level Cards**: `var(--paper-2-ref)` background for visual distinction
- **Heading Styling**: `var(--font-display)` font family, color-coded for sections
- **Table Styling**: Global `.data-table` and `.data-table--nested` classes
- **Status Badges**: Global `.status` classes (active, inactive)
- **Button Styling**: Global button styles with variants (primary, danger, small)
- **Empty State**: Global `.empty-state` styling

### Navigation & Interactions
- **Create New Chain**: Toggles form visibility, resets form data
- **Add Level**: Adds new approval level to form
- **Remove Level**: Removes level and renumbers remaining levels
- **Level Changes**: Updates role_id or auto_escalation_sla_hours for specific level
- **Form Submit**: Creates new approval chain via API, fetches updated chains
- **Activate Chain**: Deactivates current active chain, activates selected chain via API
- **Form Cancellation**: Hides form, resets form data

### Data Displayed
- **Approval Chains**: Array of chain objects from API
- **Active Chain**: Currently active chain from separate API endpoint
- **Chain Fields**: chain_version_id, levels (array), is_active, created_at, created_by
- **Level Fields**: level (number), role_id (UUID), auto_escalation_sla_hours (number)
- **Level Configuration**: Dynamic array of levels with auto-incrementing level numbers

---

## Settings — `/settings`

### Purpose
System settings and master data management interface with tabbed navigation and configuration API integration.

### Layout Structure
- Header with title and add setting button
- Tabbed navigation between Settings and Master Data
- Settings tab with table display and add/edit forms
- Master Data tab with placeholder content
- Inline form for setting creation/editing

### Responsive behavior (CRITICAL — audit this carefully per screen)
- Does this screen currently have responsive/breakpoint logic? List exact breakpoints (px values) if defined in CSS/Tailwind config/media queries
- What changes at each breakpoint currently (columns collapse, sidebar hides, nav becomes hamburger, etc.)
- Flag anything that is CURRENTLY BROKEN or NOT HANDLED at smaller widths:
  - Tables/grids with many columns that have no mobile fallback
  - Fixed-width elements (px instead of %/rem/fr) that will overflow on small screens
  - Text or buttons that get cut off, truncated, or overlap at narrow widths
  - Modals/dropdowns/tooltips that may overflow viewport on mobile
  - Horizontal scroll present (intentional or accidental)
  - Touch target sizes (are buttons/links big enough for touch, or clearly mouse-only e.g. hover-only menus)
- Note the CSS framework/approach used for responsiveness (Tailwind breakpoints, CSS Grid, media queries, container queries, none)

Also add to the GLOBAL DESIGN SYSTEM section at the top:
- Full list of ALL breakpoints used anywhere in the app (px values)
- Whether the app uses a mobile-first or desktop-first CSS approach
- Any components that currently have ZERO responsive handling (will just break/overflow on small screens)

### Components on This Page
- **Page Header**: "Settings & Master Data" with add setting toggle button
- **Add Setting Button**: Primary button, toggles between "Add Setting" and "Cancel"
- **Settings Tab**: Tab button for settings view
- **Master Data Tab**: Tab button for master data view
- **Settings Form**: Inline form for creating/editing settings
- **Form Heading**: "Edit Setting" or "Add New Setting"
- **Key Input**: Required text input (disabled when editing)
- **Value Textarea**: Required textarea for setting value
- **Category Select**: Dropdown for category selection (General, Security, Notifications, Integrations, Audit)
- **Description Input**: Optional text input for description
- **Submit Button**: Primary button with loading state
- **Cancel Button**: Secondary button to cancel form
- **Settings Table**: Data table for displaying all settings
- **Table Headers**: Key, Value, Category, Description, Updated, Actions
- **Key Display**: Code-styled key display
- **Value Display**: Truncated value with overflow handling
- **Category Badge**: Status badge showing category
- **Updated Date**: Formatted date string
- **Edit Button**: Small button to edit setting
- **Delete Button**: Danger button to delete setting
- **Master Data Section**: Placeholder section with info banner
- **Master Data Description**: Description of master data management features
- **Feature List**: Unordered list of potential master data types
- **Empty State**: "No settings configured" message

### Visual Styling
- **Header**: Uses global `.header` class with bottom border
- **Tabs**: Global `.tab` styling with active state
- **Config Form**: `var(--card-ref)` background, `1px solid var(--line-ref)` border, `16px` radius, `var(--shadow-ref)` shadow
- **Form Groups**: Standard spacing with labels above inputs
- **Label Styling**: Standard form label styling
- **Input Styling**: Full width, standard border and focus states
- **Table Styling**: Global `.data-table` and `.table-wrap` classes
- **Code Styling**: Monospace font, `var(--paper-2-ref)` background
- **Status Badges**: Global `.status` classes
- **Button Styling**: Global button styles with variants (primary, danger, small)
- **Info Banner**: `linear-gradient(135deg, #FEF9C3, #FDE68A)` background, `#FCD34D` border
- **Empty State**: Global `.empty-state` styling

### Navigation & Interactions
- **Add Setting Toggle**: Shows/hides inline form, resets form data
- **Tab Navigation**: Switches between Settings and Master Data views
- **Form Submit**: Creates/updates setting via configuration API, refreshes settings list
- **Form Cancellation**: Hides form, resets form data
- **Edit Setting**: Populates form with existing setting data, shows form
- **Delete Setting**: Resets setting to null via API with confirmation
- **Category Selection**: Dropdown with predefined categories

### Data Displayed
- **Settings**: Array of setting objects converted from configuration API
- **Setting Fields**: id, key, value, description, category, updated_at
- **Configuration Data**: Fetched from `/api/v1/configuration/global` endpoint
- **Category Options**: General, Security, Notifications, Integrations, Audit
- **Master Data Features**: KPI Categories, Discrepancy Categories, Role Definitions, School Types, Department Types, Reference Data Tables
- **System Settings**: System configuration options
- **Integration Settings**: External service configuration
- **Save Buttons**: Per-section save actions

### Visual Styling
- Tab navigation styling
- Form-based setting inputs
- Section-based organization

### Navigation & Interactions
- **Tab Changes**: Switches between setting categories
- **Setting Changes**: Updates configuration values
- **Save Actions**: Persists settings to backend

### Data Displayed
- **System Settings**: Configuration values
- **Master Data**: Reference data tables
- **Integration Config**: External service settings

---

## Observations — `/observations`

### Purpose
List view of KPI observations with statistics ribbon, status filtering, and expandable card layout.

### Layout Structure
- Page header with eyebrow and description
- Statistics ribbon with observation counts
- Controls bar with tabs and search
- Grid layout for observation cards
- Empty state for no results

### Responsive behavior (CRITICAL — audit this carefully per screen)
- Does this screen currently have responsive/breakpoint logic? List exact breakpoints (px values) if defined in CSS/Tailwind config/media queries
- What changes at each breakpoint currently (columns collapse, sidebar hides, nav becomes hamburger, etc.)
- Flag anything that is CURRENTLY BROKEN or NOT HANDLED at smaller widths:
  - Tables/grids with many columns that have no mobile fallback
  - Fixed-width elements (px instead of %/rem/fr) that will overflow on small screens
  - Text or buttons that get cut off, truncated, or overlap at narrow widths
  - Modals/dropdowns/tooltips that may overflow viewport on mobile
  - Horizontal scroll present (intentional or accidental)
  - Touch target sizes (are buttons/links big enough for touch, or clearly mouse-only e.g. hover-only menus)
- Note the CSS framework/approach used for responsiveness (Tailwind breakpoints, CSS Grid, media queries, container queries, none)

Also add to the GLOBAL DESIGN SYSTEM section at the top:
- Full list of ALL breakpoints used anywhere in the app (px values)
- Whether the app uses a mobile-first or desktop-first CSS approach
- Any components that currently have ZERO responsive handling (will just break/overflow on small screens)

### Components on This Page
- **Page Header**: "Observations" heading with description
- **Eyebrow**: "Observation Capture" label
- **Create Observation Button**: Primary button with + icon
- **Statistics Ribbon**: Total observations, Draft, Submitted, Verified counts
- **Controls Bar**: Tab navigation and search input
- **Tab Buttons**: All, Draft, Submitted, Verified with counts
- **Search Input**: Mini search with icon
- **Observation Cards**: Floating cards with observation information
- **Checkbox**: Visual completion indicator
- **Observation Title**: Link to observation detail
- **Category Tag**: Styled category name
- **Observer Tag**: Italicized "by {observer_name}" text
- **RAG Indicator**: Dot with RAG status label (Green/Amber/Red/N/A)
- **Date Indicator**: Formatted date with month/day display
- **Status Pill**: Color-coded status indicator
- **Expand Toggle**: Show/hide observation details
- **Detail Sections**: Description, location information, timeline
- **View Details Button**: Link to observation detail page
- **Edit Observation Button**: Primary button for editing
- **Empty State**: Icon and message when no observations found

### Visual Styling
- **Page Header**: Global `.page-head` styling
- **Ribbon**: Task-specific styling with count display
- **Tabs**: `var(--paper-2-ref)` background, rounded container
- **Tab Buttons**: Active state with `var(--card-ref)` background and shadow
- **Search Input**: `var(--card-ref)` background, `1px solid var(--line-ref)` border
- **Observation Cards**: `var(--card-ref)` background, `1px solid var(--line-ref)` border, `16px` radius
- **Priority Dots**: `var(--rose-ref)` (high/green), `var(--gold-ref)` (medium/amber), `var(--moss-ref)` (low/red)
- **Due Dates**: `var(--slate-ref)` color
- **Status Pills**: `#F2E7D6` (draft), `#DCEAE6` (submitted), `#E4EDE0` (verified), `#F0DEDA` (rejected)
- **Empty State**: Centered with icon and message
- **Category Tag**: `var(--paper-2-ref)` background, `4px` radius
- **Observer Tag**: Italic styling, `var(--slate-2-ref)` color

### Navigation & Interactions
- **Create Observation**: Navigates to `/observations/new`
- **Observation Title Link**: Navigates to `/observations/{id}`
- **Tab Navigation**: Filters observation list by status
- **Search**: Real-time filtering by title and description
- **Expand Toggle**: Shows/hide observation details
- **View Details**: Navigates to observation detail page
- **Edit Observation**: Navigates to `/observations/{id}` (same link)
- **Checkbox**: Visual indicator (no functionality)

### Data Displayed
- **Observation List**: Array of observation objects
- **Observation Fields**: id, school_id, school_name, department_id, department_name, observed_by_user_id, observer_name, observation_date, status, title, description, category_id, category_name, rag_status, created_at, updated_at
- **Statistics**: Computed counts for total, submitted, draft, verified
- **Status Values**: draft, submitted, verified, rejected
- **RAG Values**: green, amber, red

---

## Observation Form — `/observations/new` and `/observations/:id`

### Purpose
Create new observation or edit existing observation with school/department assignment and status management.

### Layout Structure
- Header with title and back button
- Form card with grouped field sections
- Info banner with important notices
- Action buttons at bottom

### Responsive behavior (CRITICAL — audit this carefully per screen)
- Does this screen currently have responsive/breakpoint logic? List exact breakpoints (px values) if defined in CSS/Tailwind config/media queries
- What changes at each breakpoint currently (columns collapse, sidebar hides, nav becomes hamburger, etc.)
- Flag anything that is CURRENTLY BROKEN or NOT HANDLED at smaller widths:
  - Tables/grids with many columns that have no mobile fallback
  - Fixed-width elements (px instead of %/rem/fr) that will overflow on small screens
  - Text or buttons that get cut off, truncated, or overlap at narrow widths
  - Modals/dropdowns/tooltips that may overflow viewport on mobile
  - Horizontal scroll present (intentional or accidental)
  - Touch target sizes (are buttons/links big enough for touch, or clearly mouse-only e.g. hover-only menus)
- Note the CSS framework/approach used for responsiveness (Tailwind breakpoints, CSS Grid, media queries, container queries, none)

Also add to the GLOBAL DESIGN SYSTEM section at the top:
- Full list of ALL breakpoints used anywhere in the app (px values)
- Whether the app uses a mobile-first or desktop-first CSS approach
- Any components that currently have ZERO responsive handling (will just break/overflow on small screens)

### Components on This Page
- **Page Header**: "Create Observation" or "Edit Observation" with back button
- **Back Button**: Secondary button linking to `/observations`
- **Form Card**: Container for observation fields
- **Title Input**: Optional text input for observation title
- **Description Textarea**: Required textarea for detailed description
- **School Select**: Required dropdown for school selection (populated from API)
- **Department Select**: Optional dropdown for department selection (populated based on school)
- **Observation Date Input**: Required date input (defaults to today)
- **Status Select**: Dropdown for status (Draft, Submitted, Verified, Rejected)
- **Category ID Input**: Optional text input for category UUID
- **Info Banner**: Yellow gradient banner with important notice about submission workflow
- **Cancel Button**: Secondary button to return to list
- **Submit Button**: Primary button with loading state

### Visual Styling
- **Header**: Uses global `.header` class with bottom border
- **Form Card**: `var(--card-ref)` background, `1px solid var(--line-ref)` border, `16px` radius, `var(--shadow-ref)` shadow
- **Form Groups**: Standard spacing with labels above inputs
- **Form Row**: Grid layout for paired inputs
- **Label Styling**: `0.875rem`, weight 600, `var(--ink-ref)` color
- **Input Styling**: Full width, `0.75rem 1rem` padding, `1.5px solid var(--line-ref)` border, `10px` radius
- **Input Focus**: `var(--ink-ref)` border color with shadow
- **Input Disabled**: `var(--paper-2-ref)` background, not-allowed cursor
- **Select Styling**: Same as input styling
- **Info Banner**: `linear-gradient(135deg, #FEF9C3, #FDE68A)` background, `#FCD34D` border, `#713F12` color
- **Button Styling**: Global button styles with variants (primary, secondary)

### Navigation & Interactions
- **Back Button**: Navigates to `/observations`
- **School Selection**: Triggers department population via API
- **Form Submit**: Creates/updates observation via API, then navigates to list
- **Form Validation**: HTML5 required validation + API validation
- **Loading State**: Button shows "Saving…" during API call
- **Department Dependency**: Department dropdown disabled until school is selected

### Data Displayed
- **Form Data**: school_id, department_id, observation_date, title, description, category_id, status
- **Schools List**: Array of school objects from API (up to 100)
- **Departments List**: Array of department objects filtered by school_id (up to 100)
- **Edit Mode**: Pre-populated with existing observation data
- **Create Mode**: Empty form with default values (today's date, draft status)
- **User Context**: Current user ID from localStorage for observed_by_user_id

---

## Complete Signup — `/auth/complete-signup`

### Purpose
Complete user registration process with school code assignment for account provisioning.

### Layout Structure
- Centered card layout
- Simple form with email display and school code input
- Success state with redirect message

### Responsive behavior (CRITICAL — audit this carefully per screen)
- Does this screen currently have responsive/breakpoint logic? List exact breakpoints (px values) if defined in CSS/Tailwind config/media queries
- What changes at each breakpoint currently (columns collapse, sidebar hides, nav becomes hamburger, etc.)
- Flag anything that is CURRENTLY BROKEN or NOT HANDLED at smaller widths:
  - Tables/grids with many columns that have no mobile fallback
  - Fixed-width elements (px instead of %/rem/fr) that will overflow on small screens
  - Text or buttons that get cut off, truncated, or overlap at narrow widths
  - Modals/dropdowns/tooltips that may overflow viewport on mobile
  - Horizontal scroll present (intentional or accidental)
  - Touch target sizes (are buttons/links big enough for touch, or clearly mouse-only e.g. hover-only menus)
- Note the CSS framework/approach used for responsiveness (Tailwind breakpoints, CSS Grid, media queries, container queries, none)

Also add to the GLOBAL DESIGN SYSTEM section at the top:
- Full list of ALL breakpoints used anywhere in the app (px values)
- Whether the app uses a mobile-first or desktop-first CSS approach
- Any components that currently have ZERO responsive handling (will just break/overflow on small screens)

### Components on This Page
- **Page Header**: "Complete Your Account Setup" title
- **Welcome Message**: Personalized greeting with user's full name
- **Email Display**: Disabled email input showing user's email from Clerk
- **School Code Input**: Required text input for school assignment
- **School Code Hint**: Small text listing available school codes
- **Error Message**: Error banner for failed account creation
- **Submit Button**: Primary button with loading state
- **Auth Links**: Link to dashboard for already-completed users
- **Success State**: Success message with redirect countdown

### Visual Styling
- **Auth Form**: Uses global `.auth-form` styling from App.css
- **Card Background**: `var(--card-ref)` (#FFFFFF)
- **Card Border**: `1px solid var(--line-ref)` (#E3DDCE)
- **Card Radius**: `20px`
- **Card Shadow**: `var(--shadow)`
- **Heading**: `1.5rem`, `var(--font-display)`, weight 600, `var(--ink-ref)` color
- **Description**: `0.95rem`, `var(--slate-2-ref)` color
- **Form Groups**: Standard spacing with labels above inputs
- **Label Styling**: `0.875rem`, weight 600, `var(--ink-ref)` color
- **Input Styling**: Full width, `0.75rem 1rem` padding, `1px solid var(--line-ref)` border, `8px` radius
- **Input Focus**: `var(--accent)` border color
- **Input Disabled**: Not-allowed cursor, reduced opacity
- **Small Text**: `0.75rem`, `var(--slate-2-ref)` color
- **Error Banner**: `rgba(220, 38, 38, 0.1)` background, `1px solid rgba(220, 38, 38, 0.3)` border, `#dc2626` color
- **Success State**: `#16a34a` color for heading, centered layout
- **Button Styling**: Global button styles with primary variant

### Navigation & Interactions
- **Form Submit**: Creates user account via auto-link API, sets auth cookie, redirects to dashboard
- **Auto-redirect**: Checks provisioning status on load, redirects if already provisioned
- **Dashboard Link**: Direct navigation to dashboard for users who completed setup
- **Loading State**: Button shows "Creating Account..." during API call
- **Success Redirect**: 2-second delay before redirect to dashboard

### Data Displayed
- **User Profile**: Full name and email from Clerk user object
- **Form Data**: school_code for school assignment
- **Available School Codes**: GUR-JAI, GUR-VAR, GUR-MOT, GUR-GWA, GUR-RAN, GUR-IND, GUR-MUZ, GUR-GUR, GUR-FAR, GUR-LUC, GUR-SUR, GUR-BHO
- **Provisioning Status**: Valid/invalid user provisioning from backend verification

---

This design inventory documents the current state of the School Operations & Governance Platform frontend as of the analysis date. All styling is custom-built using CSS variables and follows the established design system outlined in the Global Design System section.