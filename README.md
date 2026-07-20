# JamSession Lab

**JamSession Lab** is a full-stack Django website for organising and managing live jam session music events in Ireland. Members can discover upcoming jams, RSVP, share photos and videos, and take part in a moderated community forum.

## Quick Links

* [Live Site](https://jamsessionlab.ie)
* [GitHub Repository](https://github.com/Drake-Designer/JamSession-Lab)
* [Instagram](https://www.instagram.com/jamsessionlab)

## Contents

* [Project Overview](#project-overview)
* [How JamSession Lab Works](#how-jamsession-lab-works)
* [Feature Summary](#feature-summary)
* [Features](#features)
* [Pages Overview](#pages-overview)
* [User Experience and Brand](#user-experience-and-brand)
* [Technical Overview](#technical-overview)
* [Django Apps Structure](#django-apps-structure)
* [Frontend Structure and Static Assets](#frontend-structure-and-static-assets)
* [Technologies Used](#technologies-used)
* [Security and Error Handling](#security-and-error-handling)
* [Moderation Workflow](#moderation-workflow)
* [Database Design](#database-design)
* [Admin Panel](#admin-panel)
* [Email System](#email-system)
* [Testing](#testing)
* [Running the Project Locally](#running-the-project-locally)
* [Deployment](#deployment)
* [Future Improvements](#future-improvements)
* [Credits and Acknowledgements](#credits-and-acknowledgements)

---

## Project Overview

**JamSession Lab** is a community platform built for musicians who want to find, join, and remember real jam sessions in Ireland.

The site is not just an event calendar. It brings together:

* Public pages that explain what JamSession Lab is and who organises it
* Upcoming events with clear registration (RSVP) flows
* Member profiles with instruments, genres, experience, and social links
* A photo and video gallery from past events
* A community forum where members can post, comment, like, and share media

All user-uploaded content (gallery items, community posts, and comments) goes through an **admin approval queue** before it becomes publicly visible. This keeps the public site safe and on-brand.

The public site is always **brand-dark** (black, bold red, and white). The admin panel uses **django-unfold** and follows the system light/dark preference.

Public-facing language is **English (UK)**. Time zone is **Europe/Dublin**.

### What You Get

* A modern marketing home page with carousel and next-event preview
* Secure account system (register, login, logout, email verification, password reset)
* Rich member profiles with badges and profile completion tracking
* Event listings with Open Mic / Open Jam RSVP options and song lists
* Moderated gallery and community forum
* Staff tools for event management, moderation, and member announcements
* SEO basics (meta tags, Open Graph, JSON-LD, sitemap, robots.txt)

### Who It Is For

* Musicians looking for jam sessions in Ireland
* Returning members who want to RSVP, upload media, and join discussions
* Organisers and staff who need to manage events and moderate content
* Developers who want to study a modular, production-oriented Django project

---

## How JamSession Lab Works

1. Visitors browse the home page, about page, events, and public gallery without an account.
2. Users register with name, email, display name, and instrument details.
3. A verification email is sent. Until the email is verified, most member areas are soft-blocked.
4. Verified members can edit their profile, RSVP to events, upload gallery media, and post in the community.
5. Staff review pending gallery items, posts, and comments before they go live.
6. Organisers create and manage events, open or close registrations, and can email members about a jam.

---

## Feature Summary

### Homepage and Public Site

* Image carousel managed from the admin panel
* Short explanation of JamSession Lab
* Preview of the next upcoming event with a clear call to action
* About page with organiser profiles
* Contact form with honeypot and rate limiting
* Terms and Privacy pages
* Fully responsive layout for desktop, tablet, and mobile

### Accounts and Profiles

* Custom user model from the first migration
* Email verification with resend limits and cooldown
* Password reset via branded email
* Profile picture upload with focal-point cropping
* Instruments and preferred genres (including “Other” free-text fields)
* Irish county and town/city location fields
* Age computed from date of birth (never stored as a fixed number)
* Years of experience derived from a start year
* Social / music links (Spotify, YouTube, Instagram, and more)
* Membership badges (Founder, STAFF, Member, New Member)
* Account settings for email change and password change
* Account deletion

### Events and Registrations

* Public event list and detail pages
* Staff create / edit / delete events
* Toggle event active state and open/close registrations
* RSVP with Open Mic and Open Jam options
* Optional original songs (title, key, basic chords)
* Staff attendee lists
* Attendance status fields for tracking no-shows (`unknown` / `attended` / `no_show`)
* Manual event announcement emails to members

### Gallery and Community

* Public gallery of approved photos and videos
* Batch upload for authenticated members
* Community posts with optional cover image and media attachments
* Comments, likes, and edit/delete for own content
* Shared moderation model for pending / approved / rejected content
* On-site moderation queue and Admin Tool for staff

---

## Features

### User Authentication

* **Registration** — Create an account with required identity and instrument fields
* **Unique email** — One account per email address
* **Email verification** — Mandatory verification before full member access
* **Soft-block middleware** — Unverified users can still use public pages; member areas redirect to a clear verification screen
* **Login / logout** — Secure session authentication (logout is POST-only)
* **Password reset** — Full reset flow with emailed link
* **Password change** — Available from Account Settings when logged in
* **Email change** — Pending email address until the new address is confirmed
* **Account deletion** — Permanent deletion with cleanup of related content where configured

### User Profiles

* **Own profile and public profile** — View your page or another member’s public profile by username
* **Display name** — Public nickname (unique, max 20 characters, spaces allowed)
* **Profile picture** — Upload, replace, or remove; HEIC/HEIF supported; Cloudinary storage
* **Focal point** — X/Y focus percentages so circular crops keep the important part of the photo
* **Privacy flags** — Age and location can be hidden from the public profile
* **Phone number** — Private contact field (not shown publicly); used for community WhatsApp invitation context
* **Profile completion** — Percentage based on key profile fields, with UI hints for missing items
* **Badges** — Visual membership status across the site

### Events

* **Public browsing** — List and detail pages for active events
* **Next event on home** — Home page highlights the next upcoming jam
* **Staff management dashboard** — Create events, edit details, manage posters and descriptions
* **Registration controls** — Open or close RSVPs independently of the event remaining active
* **Notify members** — Staff can send an announcement email for a specific event

### Event Registrations (RSVP)

* **Register for an event** — Authenticated, verified members can RSVP while registrations are open
* **Open Mic / Open Jam** — Choose how you want to take part
* **Original songs** — Add song titles, keys, and basic chords when relevant
* **Instrument and experience snapshots** — Stored on the registration so staff see what the member played at sign-up time
* **Edit or cancel RSVP** — Members can update or cancel before the event policy blocks it
* **Confirmation page** — Clear success state after registering
* **Staff attendee list** — Organisers can review who is coming

### Gallery

* **Public gallery** — Approved images and videos only
* **Member upload** — Authenticated upload flow with batch support
* **Moderation** — New uploads start as pending (staff/superuser uploads can auto-approve)
* **Cloudinary cleanup** — Rejected or deleted media can purge remote assets
* **Large uploads** — File size limits configured for media-heavy use (images and videos)

### Community Forum

* **Post list and detail** — Browse approved discussions
* **Create / edit / delete posts** — Authors manage their own posts
* **Cover images** — Optional cover with focal-point support
* **Media attachments** — Images/videos on posts and comments
* **Comments** — Threaded discussion under posts
* **Likes** — One like per user per post
* **Members sidebar** — Community context for browsing other members
* **Moderation queue** — Staff approve, reject (with optional reason), or delete content
* **Admin Tool** — Staff overview with previews and bulk actions

### Public Pages and SEO

* **Home, About, Contact, Terms, Privacy**
* **Contact form** — Honeypot field + short rate limit to reduce spam
* **Sitemap** — Static pages, events, and verified public profiles
* **robots.txt** — Points crawlers to the sitemap
* **Meta / Open Graph / Twitter cards** — Per-page SEO context
* **JSON-LD** — Structured data for search engines

### Staff and Permissions

* **Staff group sync** — `is_staff` keeps a Django “Staff” group in sync
* **Content permissions** — Staff get full CRUD on events, gallery, community, and related models
* **User safety** — Staff can view/change users but only superusers can delete user accounts
* **On-site tools** — Moderation and event manage views outside the Django admin where useful

---

## Pages Overview

| Page | URL | Access | Description |
| --- | --- | --- | --- |
| Home | `/` | Public | Carousel, intro, next upcoming event |
| About | `/about/` | Public | Who we are and organiser profiles |
| Terms | `/terms/` | Public | Terms of use |
| Privacy | `/privacy/` | Public | Privacy information |
| Contact | `/contact/` | Public | Contact form |
| Gallery | `/gallery/` | Public | Approved photos and videos |
| Gallery upload | `/gallery/upload/` | Authenticated | Upload media for moderation |
| Community | `/community/` | Public (approved content) | Forum list |
| Post detail / CRUD | `/community/...` | Mixed | View approved posts; authors manage own content |
| Moderation | `/community/moderate/` | Staff | Approve / reject queue |
| Admin Tool | `/community/admin-tool/` | Staff | Staff content overview |
| Events | `/events/` | Public | Event list |
| Event detail | `/events/<id>/` | Public | Event details and RSVP entry |
| Event manage / create | `/events/manage/`, `/events/create/` | Staff | Organiser tools |
| RSVP | `/events/<id>/register/` | Authenticated + verified | Register for a jam |
| Register | `/accounts/register/` | Public | Create an account |
| Login | `/accounts/login/` | Public | Sign in |
| Logout | `/accounts/logout/` | Authenticated | Sign out (POST) |
| Verify email | `/accounts/verify-email/...` | Mixed | Verification and resend flow |
| Profile | `/accounts/profile/` | Authenticated | Own profile |
| Public profile | `/accounts/profile/<username>/` | Public | Another member’s public page |
| Profile edit | `/accounts/profile/edit/` | Authenticated | Edit profile fields |
| Account settings | `/accounts/settings/` | Authenticated | Email and password settings |
| Password reset | `/accounts/password-reset/` | Public | Reset flow |
| Admin | `/admin/` | Staff | Django Unfold admin |
| Sitemap | `/sitemap.xml` | Public | SEO sitemap |
| Robots | `/robots.txt` | Public | Crawler rules |

---

## User Experience and Brand

### Brand identity

| Token | Value | Use |
| --- | --- | --- |
| Black | `#000000` | Main background |
| Bold red | `#E63946` | Accents and primary CTAs |
| White | `#FFFFFF` | Primary text and contrast |
| Dark greys | `#1A1A1A`, `#262626` | Surfaces and secondary backgrounds |

The logo and favicon set live under `jamsession/static/images/`.

### Design principles in this project

* **No inline CSS or JavaScript in templates** — styles and scripts live in dedicated static files per page or component
* **Template inheritance** — every page extends `pages/templates/base.html`
* **Motion with purpose** — Alpine.js for UI state (navbar, modals), AOS for scroll reveals, Swiper for carousel behaviour
* **Accessibility-minded patterns** — semantic structure, focus-friendly controls, branded confirmation modals instead of raw browser dialogs where possible

### Typography and frontend libraries

* Tailwind CSS via CDN during development (config extracted to `pages/static/pages/js/tailwind-config.js`)
* Inter via Google Fonts
* Alpine.js, AOS, and Swiper (Swiper is vendored under the pages static folder)

---

## Technical Overview

### Architecture

JamSession Lab follows Django’s **MVT** pattern with a modular app layout:

* Business rules live in models, forms, and small helper modules
* Views stay focused on request/response handling
* Shared concerns (moderation, Cloudinary delivery, HEIC conversion, admin mixins) live in the `jamsession` project package

### Custom user model first

`AUTH_USER_MODEL = "accounts.User"` was set from the beginning. The custom user extends `AbstractUser` and owns all profile fields directly (no separate profile table), plus related `SocialLink` rows.

### Shared moderation base

Gallery items, community posts, and community comments inherit from `jamsession.moderation.ModeratedContent`:

* Status: `pending` → `approved` or `rejected`
* Optional rejection reason
* Approval metadata (`approved_by`, `approved_at`)
* Staff/superuser content can be auto-approved

This keeps moderation behaviour consistent across apps.

### Media pipeline

* Uploads go to **Cloudinary** via `django-cloudinary-storage`
* **Pillow** + **pillow_heif** allow HEIC/HEIF photos from phones
* Delivery helpers build web-friendly image URLs
* Cleanup helpers remove orphaned Cloudinary assets when content is rejected or deleted

### Email

Transactional email prefers the **Resend HTTPS API** (`RESEND_API_KEY`). Local development can use Django’s console email backend so messages print in the terminal.

### Database

Production and local development both use **PostgreSQL** (Neon) through `DATABASE_URL` and `dj-database-url`. The project expects `DATABASE_URL` to be set; it will not start without it.

---

## Django Apps Structure

| App / package | Responsibility |
| --- | --- |
| `accounts` | Custom user, auth flows, verification middleware, profiles, badges, staff permissions, account emails |
| `pages` | Home, About, Terms, Privacy, Contact, carousel, organisers, SEO/sitemaps, base template, global static assets, error pages |
| `events` | Event model, public list/detail, staff CRUD and manage tools, announcement emails |
| `registrations` | RSVP models and views (register, edit, cancel, confirmation, staff attendee lists) |
| `community` | Forum posts, comments, likes, media, moderation queue, Admin Tool |
| `gallery` | Moderated gallery items and upload flows |
| `jamsession` | Settings, URLs, WSGI/ASGI, shared moderation, storage helpers, Cloudinary utilities, image format helpers |

---

## Frontend Structure and Static Assets

### Base template

`pages/templates/base.html` defines:

* HTML document shell and SEO blocks
* Navbar and footer
* Global CSS/JS includes (Tailwind config, `base.css`, Alpine, AOS, confirm modal)
* Message alerts

Pages override content blocks and load page-specific CSS/JS with `{% block extra_css %}` / `{% block extra_js %}` patterns.

### Static organisation (examples)

```text
pages/static/pages/
├── css/          → base.css, home.css, about.css, navbar.css, ...
├── js/           → navbar.js, aos-init.js, tailwind-config.js, confirm-modal.js, ...
└── vendor/       → vendored libraries (e.g. Swiper)

accounts/static/accounts/
├── css/          → forms, profile, badges, settings, ...
└── js/           → profile picture widget, social links formset, ...

community/static/community/
gallery/static/gallery/
events/static/events/
registrations/static/registrations/
jamsession/static/images/   → logo and favicons
```

**Rule:** templates contain structure and Django tags only — not embedded styling or scripting (except the minimum required by third-party CDN setup).

### Production static files

**WhiteNoise** serves collected static files in production. Run `collectstatic` as part of deploy.

---

## Technologies Used

### Core

* **Python 3.14**
* **Django 6.0.7**
* **PostgreSQL** (Neon) via **psycopg** and **dj-database-url**
* **gunicorn**

### Media and storage

* **Cloudinary** + **django-cloudinary-storage**
* **Pillow**
* **pillow_heif** (HEIC/HEIF support)

### Admin

* **django-unfold**
* **django-admin-sortable2** (carousel slides and about organisers ordering)

### Frontend

* **HTML5 / CSS3 / JavaScript**
* **Tailwind CSS** (CDN during early/mid development)
* **Alpine.js**
* **AOS** (Animate On Scroll)
* **Swiper.js**
* **Google Fonts (Inter)**

### Email and ops

* **Resend** (transactional email API)
* **WhiteNoise** (static files)
* **python-dotenv** (`.env` loading)
* **Git** + **GitHub**
* Hosting target: **Render** with custom domain **jamsessionlab.ie**

### Testing

* Django’s built-in test framework (`python manage.py test`)

---

## Security and Error Handling

### Practices used in this project

* Secrets and service keys loaded from environment variables (`.env` locally, host config in production)
* `.env` is gitignored; `.env.example` documents required variables without real secrets
* CSRF protection on forms; logout and destructive actions use POST
* Server-side validation on forms and models
* Email verification gate for member features
* Ownership checks on edit/delete of user content
* Staff/superuser separation for dangerous actions (for example user deletion)
* Production hardening when `DJANGO_DEBUG` is not `True`: secure cookies, SSL redirect, HSTS
* Proxy header support (`X-Forwarded-Proto`) for Render-style HTTPS termination

### Custom error pages

Themed handlers for **400**, **403**, **404**, and **500** are wired in the project URLconf and rendered through the pages app so errors still feel like JamSession Lab.

---

## Moderation Workflow

User-generated media and forum content is **not** public by default.

1. A member uploads a gallery item or creates a post/comment.
2. The record is saved with status **pending** (unless the author is staff/superuser and auto-approval applies).
3. Staff review items in:
   * `/community/moderate/`
   * `/community/admin-tool/`
   * Django admin (Unfold sidebar includes pending filters)
4. Staff **approve** (content goes live) or **reject** (optionally with a reason).
5. Rejected or deleted media can be removed from Cloudinary to avoid orphaned files.

This workflow is central to keeping a public music community safe and presentable.

---

## Database Design

### Core entities

* **User** — Custom auth user with profile fields, verification state, badges, and privacy flags
* **SocialLink** — Ordered links belonging to a user (max five on the edit form)
* **HomeCarouselSlide** — Homepage carousel images
* **AboutOrganiser** — About page organiser cards
* **Event** — Jam session event (venue, schedule, poster, registration flags)
* **EventRegistration** — RSVP linking a user to an event (unique together)
* **RegistrationSong** — Songs attached to a registration
* **GalleryItem** — Moderated image/video
* **CommunityPost** / **CommunityComment** / media / likes — Forum graph with moderation

### Important relationships

* User → SocialLink: one-to-many
* User → EventRegistration → Event: many-to-many through registrations
* EventRegistration → RegistrationSong: one-to-many
* User → GalleryItem / CommunityPost / CommunityComment: authorship
* CommunityPost → likes and media attachments
* Moderated models share approval fields via the abstract `ModeratedContent` base

### Design choices worth noting

* Age and years of experience are **derived**, not stored as static integers that go stale
* Registration stores **snapshots** of instrument/experience so historical RSVPs stay meaningful if the profile changes later
* Attendance status exists on registrations to support reducing no-shows over time
* Irish location data uses county + town/city validation lists in `accounts/constants.py`

---

## Admin Panel

The admin uses **django-unfold** with a JamSession Lab branded sidebar.

Staff can manage:

* Homepage carousel slides (sortable)
* About organisers (sortable)
* Users
* Events and registrations
* Gallery items (including pending filter links)
* Community posts and comments (including pending filter links)

Day-to-day moderation can also happen on the public site via the community moderation views, which is often faster on a phone at a venue.

Create a local superuser with:

```bash
python manage.py createsuperuser
```

---

## Email System

Emails are sent for:

* Email verification (with resend limits)
* Password reset
* Email change confirmation and notice
* New user alerts to superusers
* Contact form messages to the staff inbox
* Event announcement emails to members

Templates live under app email template folders (for example `accounts/templates/accounts/emails/`).

**Production:** Resend + verified domain (`jamsessionlab.ie`), typically sending as `staff@jamsessionlab.ie`.

**Local development:** set the console email backend in `.env` to print messages in the terminal instead of sending real mail.

---

## Testing

The project includes a large Django test suite across:

* `accounts/tests.py`
* `accounts/tests_staff_permissions.py`
* `pages/tests.py`
* `events/tests.py`
* `registrations/tests.py`
* `gallery/tests.py`
* `community/tests.py`

Run tests with:

```bash
python manage.py test
```

If you use a hosted Postgres provider such as Neon for local development, `--keepdb` can avoid slow or flaky test database creation:

```bash
python manage.py test --keepdb
```

---

## Running the Project Locally

### Requirements

* Python 3.14+
* A PostgreSQL database (Neon free tier works well)
* Cloudinary account (for media uploads)
* Optional: Resend API key (or console email backend)

### Quick start

```bash
# Clone the repository
git clone https://github.com/Drake-Designer/JamSession-Lab.git
cd JamSession-Lab

# Create and activate a virtual environment
python -m venv .venv

# Windows PowerShell
.venv\Scripts\Activate.ps1

# macOS / Linux
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create your environment file
cp .env.example .env
# Then edit .env with your real values

# Apply migrations
python manage.py migrate

# Create an admin user (optional)
python manage.py createsuperuser

# Run the development server
python manage.py runserver
```

Open [http://127.0.0.1:8000/](http://127.0.0.1:8000/).

### Environment configuration

Copy `.env.example` to `.env` and fill in at least:

| Variable | Purpose |
| --- | --- |
| `SECRET_KEY` | Django cryptographic signing |
| `DJANGO_DEBUG` | `True` for local development |
| `DJANGO_ALLOWED_HOSTS` | e.g. `127.0.0.1,localhost` |
| `DATABASE_URL` | PostgreSQL connection string (required) |
| `CLOUD_NAME`, `API_KEY`, `API_SECRET` | Cloudinary media |
| `RESEND_API_KEY` | Transactional email (or use console backend) |
| `DEFAULT_FROM_EMAIL` | From address shown to users |
| `CONTACT_EMAIL` | Inbox for contact form messages |
| `SITE_URL` | Canonical public origin for SEO links |

Never commit `.env`. If a secret is exposed, rotate it immediately.

### Generate a Django secret key

```bash
python manage.py shell -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

---

## Deployment

The production site is intended for **Render** (or similar) with:

* **gunicorn** as the WSGI server
* **WhiteNoise** for static files
* **Neon PostgreSQL** as the database
* **Cloudinary** for media
* **Resend** for email
* Custom domain **https://jamsessionlab.ie**

Typical production environment variables mirror `.env.example`, with:

* `DJANGO_DEBUG=False`
* `DJANGO_ALLOWED_HOSTS` including `jamsessionlab.ie` (and `www` if used)
* `DJANGO_CSRF_TRUSTED_ORIGINS` including the HTTPS origins
* `DATABASE_URL` pointing at the production database
* Cloudinary and Resend credentials configured
* `SITE_URL=https://jamsessionlab.ie`

On each release, run migrations and collect static files, for example:

```bash
python manage.py migrate --noinput
python manage.py collectstatic --noinput
```

Exact build/start commands depend on the host dashboard settings.

---

## Future Improvements

Ideas on the roadmap (not all required for a first public launch):

* Stronger attendance check-in UI for organisers on the night of a jam
* Public member directory with privacy-aware filters
* Compiled Tailwind build (replace CDN) before long-term production hardening
* Further pagination and query optimisation as community/gallery data grows
* Richer Privacy Policy polish for GDPR / Ireland-specific wording as legal copy is finalised
* Optional Redis/Celery later if background email volume grows beyond threaded sends

---

## Credits and Acknowledgements

### Built with

* [Django Documentation](https://docs.djangoproject.com/) — models, auth, forms, admin, security guidance
* [django-unfold](https://unfoldadmin.com/) — modern admin theme
* [Cloudinary](https://cloudinary.com/documentation) — media storage and delivery
* [Resend](https://resend.com/docs) — transactional email
* [Tailwind CSS](https://tailwindcss.com/), [Alpine.js](https://alpinejs.dev/), [AOS](https://michalsnik.github.io/aos/), [Swiper](https://swiperjs.com/) — frontend tooling
* [Neon](https://neon.tech/) — hosted PostgreSQL
* [Render](https://render.com/) — application hosting

### Project

JamSession Lab is an independent project by [Drake-Designer](https://github.com/Drake-Designer), built to support real jam session communities in Ireland.

### Special thanks

Thanks to early testers and musicians who tried the registration, profile, gallery, and community flows and helped catch real-world UX issues before public launch.

---

## Licence

Private repository. All rights reserved unless otherwise stated by the owner.
