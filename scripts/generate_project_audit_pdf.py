"""
Generate a full technical audit PDF for JamSession Lab on the user's Desktop.
Run: python scripts/generate_project_audit_pdf.py
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    KeepTogether,
    ListFlowable,
    ListItem,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

OUTPUT_PATH = Path.home() / "Desktop" / "JamSession_Lab_Audit_Completo.pdf"
BRAND_RED = colors.HexColor("#E63946")
BRAND_BLACK = colors.HexColor("#111111")
LIGHT_GREY = colors.HexColor("#F5F5F5")
MID_GREY = colors.HexColor("#666666")
LINE_GREY = colors.HexColor("#DDDDDD")


def build_styles() -> dict:
    base = getSampleStyleSheet()
    styles = {
        "cover_title": ParagraphStyle(
            "cover_title",
            parent=base["Title"],
            fontName="Helvetica-Bold",
            fontSize=26,
            leading=32,
            textColor=BRAND_BLACK,
            alignment=TA_CENTER,
            spaceAfter=8,
        ),
        "cover_sub": ParagraphStyle(
            "cover_sub",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=12,
            leading=16,
            textColor=MID_GREY,
            alignment=TA_CENTER,
            spaceAfter=6,
        ),
        "h1": ParagraphStyle(
            "h1",
            parent=base["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=16,
            leading=20,
            textColor=BRAND_RED,
            spaceBefore=16,
            spaceAfter=10,
        ),
        "h2": ParagraphStyle(
            "h2",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=12,
            leading=16,
            textColor=BRAND_BLACK,
            spaceBefore=12,
            spaceAfter=6,
        ),
        "body": ParagraphStyle(
            "body",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=9.5,
            leading=13,
            textColor=BRAND_BLACK,
            alignment=TA_JUSTIFY,
            spaceAfter=6,
        ),
        "bullet": ParagraphStyle(
            "bullet",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=9.5,
            leading=13,
            textColor=BRAND_BLACK,
            leftIndent=4,
        ),
        "meta": ParagraphStyle(
            "meta",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=8.5,
            leading=11,
            textColor=MID_GREY,
            alignment=TA_CENTER,
        ),
        "table_cell": ParagraphStyle(
            "table_cell",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=8,
            leading=11,
            textColor=BRAND_BLACK,
        ),
        "table_header": ParagraphStyle(
            "table_header",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=8,
            leading=11,
            textColor=colors.white,
        ),
        "footer": ParagraphStyle(
            "footer",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=8,
            textColor=MID_GREY,
            alignment=TA_CENTER,
        ),
        "toc": ParagraphStyle(
            "toc",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=10,
            leading=16,
            textColor=BRAND_BLACK,
            leftIndent=10,
        ),
    }
    return styles


def make_table(headers: list[str], rows: list[list[str]], styles: dict, col_widths=None):
    data = [[Paragraph(h, styles["table_header"]) for h in headers]]
    for row in rows:
        data.append([Paragraph(str(cell), styles["table_cell"]) for cell in row])
    table = Table(data, colWidths=col_widths, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), BRAND_BLACK),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("BACKGROUND", (0, 1), (-1, -1), colors.white),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT_GREY]),
                ("GRID", (0, 0), (-1, -1), 0.4, LINE_GREY),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return table


def bullets(items: list[str], styles: dict) -> ListFlowable:
    return ListFlowable(
        [ListItem(Paragraph(item, styles["bullet"]), leftIndent=12, bulletColor=BRAND_RED) for item in items],
        bulletType="bullet",
        start="•",
        leftIndent=12,
        bulletFontName="Helvetica",
        bulletFontSize=9,
    )


def add_header_footer(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(BRAND_RED)
    canvas.setLineWidth(1.5)
    canvas.line(1.8 * cm, A4[1] - 1.2 * cm, A4[0] - 1.8 * cm, A4[1] - 1.2 * cm)
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(MID_GREY)
    canvas.drawString(1.8 * cm, A4[1] - 1.0 * cm, "JamSession Lab — Audit tecnico completo")
    canvas.drawRightString(A4[0] - 1.8 * cm, A4[1] - 1.0 * cm, "Confidenziale")
    canvas.setStrokeColor(LINE_GREY)
    canvas.setLineWidth(0.5)
    canvas.line(1.8 * cm, 1.3 * cm, A4[0] - 1.8 * cm, 1.3 * cm)
    canvas.drawCentredString(A4[0] / 2, 0.9 * cm, f"Pagina {doc.page}")
    canvas.restoreState()


def build_document() -> None:
    styles = build_styles()
    story = []

    # Cover
    story.append(Spacer(1, 3.5 * cm))
    story.append(Paragraph("JamSession Lab", styles["cover_title"]))
    story.append(Paragraph("Audit tecnico completo del progetto", styles["cover_title"]))
    story.append(Spacer(1, 0.6 * cm))
    story.append(
        Paragraph(
            "Come funziona il sito · Stack tecnologico · Collegamenti esterni · Stato implementazione",
            styles["cover_sub"],
        )
    )
    story.append(Spacer(1, 1.2 * cm))
    story.append(
        make_table(
            ["Campo", "Valore"],
            [
                ["Data audit", date.today().strftime("%d %B %Y")],
                ["Repository", "github.com/Drake-Designer/JamSession-Lab (privato)"],
                ["Prodotto", "Piattaforma per organizzare e gestire Jam Session in Irlanda"],
                ["Lingua sito", "English (UK)"],
                ["Timezone", "Europe/Dublin"],
                ["Ambiente analizzato", "Codice locale + settings + requirements + piano operativo"],
            ],
            styles,
            col_widths=[4.5 * cm, 12 * cm],
        )
    )
    story.append(Spacer(1, 1.5 * cm))
    story.append(
        Paragraph(
            "Questo documento spiega in modo chiaro e completo l’architettura del sito, "
            "il flusso utente, le tecnologie usate e tutti i servizi esterni a cui il progetto è collegato.",
            styles["body"],
        )
    )
    story.append(PageBreak())

    # TOC
    story.append(Paragraph("Indice", styles["h1"]))
    toc_items = [
        "1. Sintesi esecutiva",
        "2. Cosa fa il sito (prodotto)",
        "3. Come funziona (flussi principali)",
        "4. Architettura Django (app e responsabilità)",
        "5. Modelli dati e relazioni",
        "6. Mappa delle pagine e URL",
        "7. Stack tecnologico e dipendenze",
        "8. Frontend (UI, CSS, JS, CDN)",
        "9. Autenticazione, profili e permessi",
        "10. Moderazione e contenuti utente",
        "11. Eventi e iscrizioni (RSVP)",
        "12. Admin panel (django-unfold)",
        "13. Collegamenti esterni e integrazioni",
        "14. Configurazione, sicurezza e variabili d’ambiente",
        "15. Cosa è già fatto e cosa manca",
        "16. Conclusioni e priorità pre-lancio",
    ]
    for item in toc_items:
        story.append(Paragraph(item, styles["toc"]))
    story.append(PageBreak())

    # 1
    story.append(Paragraph("1. Sintesi esecutiva", styles["h1"]))
    story.append(
        Paragraph(
            "JamSession Lab è un’applicazione web Django completa (non un prototipo vuoto) "
            "per gestire jam session musicali in Irlanda: utenti si registrano, verificano l’email, "
            "compilano un profilo musicale, iscrivono agli eventi, caricano media in gallery e "
            "partecipano a un forum community con moderazione staff.",
            styles["body"],
        )
    )
    story.append(
        Paragraph(
            "Il backend usa <b>Django 6.0.7</b> su <b>Python 3.14.6</b>, database "
            "<b>PostgreSQL su Neon</b>, media su <b>Cloudinary</b>, admin moderno con "
            "<b>django-unfold</b>, frontend con Tailwind (CDN), Alpine.js, AOS e Swiper.",
            styles["body"],
        )
    )
    story.append(
        Paragraph(
            "Il nucleo prodotto (accounts, gallery, community, events, registrations) è "
            "già funzionante e coperto da una suite di test ampia (~373 test dichiarati nel piano operativo). "
            "Prima del lancio pubblico restano soprattutto: SMTP reale, Privacy Policy definitiva, "
            "WhiteNoise per gli static, password reset e alcuni task di hardening.",
            styles["body"],
        )
    )

    # 2
    story.append(Paragraph("2. Cosa fa il sito (prodotto)", styles["h1"]))
    story.append(
        Paragraph(
            "Il sito pubblico è pensato per musicisti e appassionati in Irlanda. "
            "Identità visiva: nero (#000000), rosso bold (#E63946), bianco. "
            "Il frontend pubblico è sempre dark di brand; l’admin segue preferenza sistema light/dark.",
            styles["body"],
        )
    )
    story.append(Paragraph("Funzionalità principali", styles["h2"]))
    story.append(
        bullets(
            [
                "<b>Home</b>: navbar, carousel immagini, spiegazione del progetto, preview del prossimo evento con CTA di iscrizione.",
                "<b>About / Terms / Privacy / Contact</b>: pagine informative e legali (Privacy ancora in bozza).",
                "<b>Gallery</b>: foto/video approvati; upload utenti con coda di moderazione.",
                "<b>Community</b>: forum con post, commenti, like, media allegati e cover image; moderazione staff + Admin Tool.",
                "<b>Events</b>: elenco e dettaglio jam; staff crea/modifica/attiva eventi e apre/chiude le iscrizioni.",
                "<b>Registrations (RSVP)</b>: iscrizione evento, preferenze Open Mic/Jam, brani, cancellazione, liste iscritti per lo staff.",
                "<b>Accounts / Profile</b>: registrazione, login, verifica email, profilo pubblico, badge, social link, eliminazione account.",
            ],
            styles,
        )
    )

    # 3
    story.append(Paragraph("3. Come funziona (flussi principali)", styles["h1"]))

    story.append(Paragraph("3.1 Registrazione e verifica email", styles["h2"]))
    story.append(
        bullets(
            [
                "L’utente si registra con form dedicato (dati anagrafici, strumenti, ecc.).",
                "Il sistema crea l’utente, invia email di verifica (oggi solo su console, non SMTP reale) e lo autentica.",
                "Viene mostrata la pagina Welcome con link WhatsApp community.",
                "Un middleware (<b>EmailVerificationMiddleware</b>) blocca in modo soft gli utenti non verificati su molte aree protette, lasciando accessibili home, about, legal, eventi pubblici, gallery pubblica, community pubblica e le pagine di verifica.",
                "Il link nell’email contiene un token UUID; esiste anche il resend con rate-limit di sessione (60 secondi).",
            ],
            styles,
        )
    )

    story.append(Paragraph("3.2 Login / logout / profilo", styles["h2"]))
    story.append(
        bullets(
            [
                "Login accettato con email oppure username.",
                "Logout solo via POST (protezione CSRF).",
                "Profilo pubblico per username; modifica del proprio profilo, foto Cloudinary, social link, eliminazione account.",
                "Password reset: link presente ma ancora stub (<b>href=\"#\"</b>).",
                "Account Settings (cambio password/email/DoB): placeholder, non ancora implementato.",
            ],
            styles,
        )
    )

    story.append(Paragraph("3.3 Evento e RSVP", styles["h2"]))
    story.append(
        bullets(
            [
                "Home mostra il prossimo evento attivo; CTA porta al dettaglio / registrazione.",
                "Utente loggato e verificato può iscriversi se le registrations sono aperte.",
                "Durante l’RSVP può indicare Open Mic / Jam, brani (titolo, key, accordi) e note.",
                "Può modificare o cancellare la propria iscrizione (policy su eventi già iniziati / registrations chiuse ancora da raffinare).",
                "Staff vede liste iscritti e gestisce eventi da /events/manage/.",
            ],
            styles,
        )
    )

    story.append(Paragraph("3.4 Gallery e Community (con moderazione)", styles["h2"]))
    story.append(
        bullets(
            [
                "Upload gallery e contenuti community partono come <b>pending</b> (salvo staff, che può essere auto-approvato).",
                "Solo i contenuti <b>approved</b> sono pubblici.",
                "Staff usa Review Queue e Admin Tool per approvare/rifiutare/eliminare post, commenti e media gallery.",
                "Community supporta like, commenti con media, cover focus sulle immagini di copertina.",
            ],
            styles,
        )
    )
    story.append(PageBreak())

    # 4
    story.append(Paragraph("4. Architettura Django (app e responsabilità)", styles["h1"]))
    story.append(
        Paragraph(
            "Il progetto segue il pattern MVT di Django con app modulari. "
            "Il package di progetto è <b>jamsession/</b> (settings, urls, helper condivisi).",
            styles["body"],
        )
    )
    story.append(
        make_table(
            ["App / package", "Ruolo"],
            [
                ["accounts", "Custom User, auth, verifica email, profilo, badge, gruppo Staff e permessi"],
                ["pages", "Home, About, Terms, Privacy, Contact, carousel, error pages 400/403/404/500"],
                ["gallery", "Media moderati (foto/video), upload batch, lista pubblica"],
                ["community", "Forum: post, commenti, like, media, moderazione, Admin Tool, sidebar members"],
                ["events", "Modello Event, listing/detail, CRUD staff, toggle active/registrations"],
                ["registrations", "RSVP, brani, cancel, liste iscritti staff (URL montati sotto events/)"],
                ["jamsession/", "settings, moderation abstract, Cloudinary helpers, admin mixins, static brand"],
            ],
            styles,
            col_widths=[3.8 * cm, 12.7 * cm],
        )
    )
    story.append(Spacer(1, 0.35 * cm))
    story.append(
        Paragraph(
            "Convenzione di codice: poca logica nelle view, validazione nei form/model, "
            "nessun CSS/JS inline nei template (file static dedicati per pagina/componente).",
            styles["body"],
        )
    )

    # 5
    story.append(Paragraph("5. Modelli dati e relazioni", styles["h1"]))

    story.append(Paragraph("5.1 accounts.User (AUTH_USER_MODEL)", styles["h2"]))
    story.append(
        Paragraph(
            "Estende AbstractUser. Campi chiave: first_name, last_name, email unica, display_name unico, "
            "phone opzionale, profile_picture (Cloudinary), date_of_birth (età calcolata, non memorizzata), "
            "county/town_city, instruments (JSON), other_instrument, preferred_genres (JSON), other_genre, "
            "experience_started_year / experience_level, bio, is_email_verified, email_verification_token, "
            "terms_accepted_at, force_member_badge. Relazione 1-N con SocialLink.",
            styles["body"],
        )
    )

    story.append(Paragraph("5.2 Altri modelli", styles["h2"]))
    story.append(
        make_table(
            ["Modello", "App", "Note"],
            [
                ["HomeCarouselSlide", "pages", "Slide home: immagine, alt, caption, order, is_active"],
                ["GalleryItem", "gallery", "ModeratedContent; file Cloudinary; media_type; titolo/caption"],
                ["CommunityPost", "community", "Moderato; slug; cover + focus x/y; media allegati"],
                ["CommunityComment", "community", "Moderato; FK post; media allegati"],
                ["CommunityLike", "community", "Unique (post, user)"],
                ["Event", "events", "venue, address, starts_at indexed, poster, flags active/registrations_open"],
                ["EventRegistration", "registrations", "Unique (user, event); RSVP; snapshot strumenti; attendance"],
                ["RegistrationSong", "registrations", "Brani legati all’iscrizione"],
            ],
            styles,
            col_widths=[4.2 * cm, 2.8 * cm, 9.5 * cm],
        )
    )
    story.append(Spacer(1, 0.25 * cm))
    story.append(
        Paragraph(
            "La moderazione condivisa vive in <b>jamsession.moderation.ModeratedContent</b> "
            "(status pending/approved/rejected, approved_by, approved_at, rejection_reason).",
            styles["body"],
        )
    )

    # 6
    story.append(Paragraph("6. Mappa delle pagine e URL", styles["h1"]))
    story.append(
        make_table(
            ["Area", "Esempi URL", "Accesso"],
            [
                ["Pagine", "/ · /about/ · /terms/ · /privacy/ · /contact/", "Pubblico"],
                ["Accounts", "/accounts/register|login|logout|welcome|verify-email|profile/...", "Misto (auth)"],
                ["Gallery", "/gallery/ · /gallery/upload/", "Lista pubblica; upload login"],
                ["Community", "/community/ · /post/... · /moderate/ · /admin-tool/", "Pubblico + staff"],
                ["Events", "/events/ · /events/&lt;pk&gt;/ · /manage/ · /create/", "Pubblico + staff"],
                ["RSVP", "/events/&lt;pk&gt;/register/ · edit · cancel · attendees", "Login / staff"],
                ["Admin", "/admin/", "Staff / superuser"],
            ],
            styles,
            col_widths=[3 * cm, 8.5 * cm, 5 * cm],
        )
    )
    story.append(Spacer(1, 0.25 * cm))
    story.append(
        Paragraph(
            "Le view sono quasi tutte function-based; eccezione principale: LoginView (CBV). "
            "Error handler personalizzati: 400, 403, 404, 500.",
            styles["body"],
        )
    )
    story.append(PageBreak())

    # 7
    story.append(Paragraph("7. Stack tecnologico e dipendenze", styles["h1"]))
    story.append(
        make_table(
            ["Componente", "Versione / scelta"],
            [
                ["Python", "3.14.6"],
                ["Django", "6.0.7"],
                ["Database", "PostgreSQL via Neon (psycopg 3.3.4)"],
                ["Media storage", "Cloudinary 1.45.0 + django-cloudinary-storage 0.3.0"],
                ["Admin UI", "django-unfold 0.100.0"],
                ["Ordinamento admin", "django-admin-sortable2 2.3.1"],
                ["Immagini", "Pillow 12.3.0 + pillow_heif 1.4.0 (HEIC)"],
                ["Config env", "python-dotenv 1.2.2 + dj-database-url 3.1.2"],
                ["Frontend CSS", "Tailwind via CDN (Play CDN)"],
                ["Interattività", "Alpine.js 3.14.9"],
                ["Animazioni", "AOS 2.3.4"],
                ["Carousel", "Swiper (vendored localmente, non CDN)"],
                ["Font", "Google Fonts — Inter"],
                ["Email (attuale)", "django.core.mail.backends.console.EmailBackend"],
            ],
            styles,
            col_widths=[5 * cm, 11.5 * cm],
        )
    )
    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph("Dipendenze pinate in requirements.txt", styles["h2"]))
    story.append(
        Paragraph(
            "asgiref 3.12.0 · certifi 2026.6.17 · charset-normalizer 3.4.9 · cloudinary 1.45.0 · "
            "dj-database-url 3.1.2 · Django 6.0.7 · django-admin-sortable2 2.3.1 · "
            "django-cloudinary-storage 0.3.0 · django-unfold 0.100.0 · idna 3.18 · pillow 12.3.0 · "
            "pillow_heif 1.4.0 · psycopg / psycopg-binary 3.3.4 · python-dotenv 1.2.2 · "
            "requests 2.34.2 · six 1.17.0 · sqlparse 0.5.5 · tzdata 2026.3 · urllib3 2.7.0",
            styles["body"],
        )
    )
    story.append(
        Paragraph(
            "<b>Non presenti</b> (previsti o opzionali): WhiteNoise, Django REST Framework, "
            "django-allauth, Redis, SDK email (SendGrid/Mailgun), analytics, Sentry, Docker/CI.",
            styles["body"],
        )
    )

    # 8
    story.append(Paragraph("8. Frontend (UI, CSS, JS, CDN)", styles["h1"]))
    story.append(
        Paragraph(
            "Template base: <b>pages/templates/base.html</b> (lang=en-GB, tema brand-dark). "
            "Navbar sticky con Alpine, messaggi flash, footer con Terms/Privacy/Contact e credito GitHub designer. "
            "Modale di conferma condivisa in JS dedicato (niente confirm nativo, salvo residui da pulire).",
            styles["body"],
        )
    )
    story.append(Paragraph("Asset esterni (CDN)", styles["h2"]))
    story.append(
        make_table(
            ["Libreria", "URL / origine"],
            [
                ["Tailwind CSS", "https://cdn.tailwindcss.com"],
                ["Alpine.js 3.14.9", "https://cdn.jsdelivr.net/npm/alpinejs@3.14.9/dist/cdn.min.js"],
                ["AOS 2.3.4 CSS", "https://unpkg.com/aos@2.3.4/dist/aos.css"],
                ["AOS 2.3.4 JS", "https://unpkg.com/aos@2.3.4/dist/aos.js"],
                ["Google Fonts Inter", "fonts.googleapis.com (family Inter 400–900)"],
                ["Swiper", "Copia locale in pages/static/pages/vendor/swiper/"],
            ],
            styles,
            col_widths=[4.5 * cm, 12 * cm],
        )
    )
    story.append(Spacer(1, 0.25 * cm))
    story.append(
        Paragraph(
            "Gli static custom sono organizzati per app: "
            "pages (base/home/about/navbar/carousel), accounts (form/profile/badge), "
            "gallery, community (forum + moderation + admin tool), events, registrations. "
            "Config Tailwind estratta in <b>tailwind-config.js</b>.",
            styles["body"],
        )
    )

    # 9
    story.append(Paragraph("9. Autenticazione, profili e permessi", styles["h1"]))
    story.append(
        bullets(
            [
                "<b>AUTH_USER_MODEL</b> = accounts.User (impostato dall’inizio).",
                "LOGIN_URL=/accounts/login/ · redirect post-login/logout verso /.",
                "Verifica email obbligatoria di fatto per i membri (middleware soft-block).",
                "Badge: Founder / STAFF / Member / New Member (logica su model).",
                "Gruppo Django <b>Staff</b> sincronizzato via signal; può gestire utenti ma non eliminarli.",
                "Gate ripetuti _require_moderator su community/events/registrations (staff/superuser).",
            ],
            styles,
        )
    )
    story.append(PageBreak())

    # 10
    story.append(Paragraph("10. Moderazione e contenuti utente", styles["h1"]))
    story.append(
        Paragraph(
            "Gallery e Community ereditano lo stesso workflow di approvazione. "
            "I contenuti non approvati non compaiono in pubblico. "
            "Lo staff lavora da:",
            styles["body"],
        )
    )
    story.append(
        bullets(
            [
                "<b>/community/moderate/</b> — coda di review (approve / reject / delete).",
                "<b>/community/admin-tool/</b> — panoramica operativa multi-tab (gallery/post/comment) con azioni bulk.",
                "<b>/admin/</b> (Unfold) — gestione completa modelli, filtri pending, sidebar custom.",
            ],
            styles,
        )
    )
    story.append(
        Paragraph(
            "Notifiche email all’utente quando un contenuto viene approvato/rifiutato: "
            "non ancora implementate (dipendono da SMTP reale).",
            styles["body"],
        )
    )

    # 11
    story.append(Paragraph("11. Eventi e iscrizioni (RSVP)", styles["h1"]))
    story.append(
        Paragraph(
            "Un Event rappresenta una jam: venue, indirizzo, link mappa, orari, poster, descrizione, "
            "flag is_active e registrations_open. Il titolo è tipicamente generato come "
            "“JamSession @ {venue}”. Helper di model: is_upcoming, is_registration_allowed.",
            styles["body"],
        )
    )
    story.append(
        Paragraph(
            "EventRegistration collega User↔Event in modo unico, con stato RSVP "
            "(registered/cancelled), preferenze Open Mic/Jam, note, snapshot strumenti/esperienza "
            "e attendance_status (unknown/attended/no_show). "
            "L’UI di check-in attendance per lo staff non è ancora pronta (campo sì, schermata no).",
            styles["body"],
        )
    )

    # 12
    story.append(Paragraph("12. Admin panel (django-unfold)", styles["h1"]))
    story.append(
        Paragraph(
            "Admin brandizzato: SITE_TITLE “JamSession Lab Admin”, simbolo music_note, "
            "sidebar custom (Carousel, Gallery pending, Community pending, Events/Registrations, Users). "
            "show_all_applications=False. Tutti i ModelAdmin principali usano unfold.admin.ModelAdmin; "
            "carousel con ordinamento sortable2. SocialLink solo come inline sul User.",
            styles["body"],
        )
    )

    # 13 — External connections (key section)
    story.append(Paragraph("13. Collegamenti esterni e integrazioni", styles["h1"]))
    story.append(
        Paragraph(
            "Questa sezione elenca tutto ciò a cui il progetto è collegato fuori dalla macchina locale.",
            styles["body"],
        )
    )
    story.append(
        make_table(
            ["Servizio", "Ruolo nel progetto", "Stato"],
            [
                [
                    "Neon PostgreSQL",
                    "Database primario via DATABASE_URL (dj-database-url). "
                    "conn_max_age=600, health checks. Il progetto non parte senza DATABASE_URL. "
                    "db.sqlite3 locale è residuo non usato.",
                    "Attivo / obbligatorio",
                ],
                [
                    "Cloudinary",
                    "Storage e delivery di tutti i media (profili, gallery, community, poster). "
                    "Credenziali CLOUD_NAME / API_KEY / API_SECRET. secure=True. "
                    "Helper per HEIC, path delivery e cleanup.",
                    "Attivo / obbligatorio",
                ],
                [
                    "Email (console)",
                    "Backend console: le email di verifica compaiono nel terminale del server. "
                    "DEFAULT_FROM_EMAIL = JamSession Lab &lt;noreply@jamsessionlab.ie&gt;. "
                    "SMTP produzione (SendGrid/Mailgun/…) non ancora collegato.",
                    "Dev only",
                ],
                [
                    "WhatsApp",
                    "Link invite community hardcoded in settings "
                    "(chat.whatsapp.com/…), usato in welcome/community.",
                    "Link esterno",
                ],
                [
                    "Instagram",
                    "Pagina Contact punta a instagram.com/jamsessionlab. Nessuna API/OAuth.",
                    "Link esterno",
                ],
                [
                    "GitHub",
                    "Repo privato JamSession-Lab + credito footer al designer Drake-Designer.",
                    "Versionamento / credito",
                ],
                [
                    "CDN frontend",
                    "Tailwind Play CDN, jsDelivr (Alpine), unpkg (AOS), Google Fonts.",
                    "Runtime browser",
                ],
            ],
            styles,
            col_widths=[3.2 * cm, 10.3 * cm, 3 * cm],
        )
    )
    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph("Non collegato (assente oggi)", styles["h2"]))
    story.append(
        bullets(
            [
                "Social login (Google/Facebook/Apple)",
                "Analytics (GA, Plausible, ecc.)",
                "Error tracking (Sentry)",
                "Cache Redis / Memcached",
                "Object storage AWS S3 (si usa Cloudinary)",
                "CI/CD GitHub Actions, Docker, orchestrazione",
                "API REST pubblica (DRF non installato)",
                "WhiteNoise / pipeline static di produzione",
            ],
            styles,
        )
    )
    story.append(PageBreak())

    # 14
    story.append(Paragraph("14. Configurazione, sicurezza e variabili d’ambiente", styles["h1"]))
    story.append(Paragraph("Variabili richieste (.env / .env.example)", styles["h2"]))
    story.append(
        make_table(
            ["Variabile", "Scopo"],
            [
                ["SECRET_KEY", "Chiave Django obbligatoria (crash se mancante)"],
                ["DJANGO_DEBUG", "True solo in locale; default False"],
                ["DJANGO_ALLOWED_HOSTS", "Host ammessi (virgola-separati)"],
                ["CLOUD_NAME / API_KEY / API_SECRET", "Credenziali Cloudinary"],
                ["DATABASE_URL", "Connection string Neon PostgreSQL (obbligatoria)"],
            ],
            styles,
            col_widths=[5.5 * cm, 11 * cm],
        )
    )
    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph("Sicurezza già in posto", styles["h2"]))
    story.append(
        bullets(
            [
                "Nessun csrf_exempt trovato; CsrfViewMiddleware attivo.",
                ".env in .gitignore; secret e Cloudinary da env.",
                "Con DEBUG=False: SESSION/CSRF cookie secure, SSL redirect, HSTS 1 anno + preload/subdomains.",
                "XFrameOptionsMiddleware; password validators Django standard.",
                "Logout POST-only; protezione open redirect su parametro next.",
                "Upload validati (gallery/community); staff gate su tool sensibili.",
            ],
            styles,
        )
    )
    story.append(Paragraph("Rischi / gap pre-lancio", styles["h2"]))
    story.append(
        bullets(
            [
                "Email ancora console → verifica/reset password non “reali” in produzione.",
                "email_verification_token non unique=True (debito noto).",
                "Limiti upload memoria a 100 MB da rivalutare.",
                "Tailwind Play CDN e assenza WhiteNoise/STATIC_ROOT non ideali per produzione.",
                "Privacy Policy in bozza (compliance GDPR/IE incompleta).",
                "Password reset stub.",
            ],
            styles,
        )
    )

    # 15
    story.append(Paragraph("15. Cosa è già fatto e cosa manca", styles["h1"]))
    story.append(Paragraph("Implementato e funzionante", styles["h2"]))
    story.append(
        bullets(
            [
                "Accounts completo (register/login/verify/profile/social/badge/delete)",
                "Gallery + moderazione + lightbox",
                "Community completa + moderation queue + Admin Tool",
                "Events + RSVP + manage staff + next-event in home",
                "Neon + Cloudinary + Unfold admin",
                "Error pages custom; suite test ampia (~373 pass)",
            ],
            styles,
        )
    )
    story.append(Paragraph("Mancanze principali (dal piano operativo)", styles["h2"]))
    story.append(
        make_table(
            ["ID", "Voce", "Impatto"],
            [
                ["C1", "SMTP reale (SendGrid/Mailgun/…)", "Critico pre-lancio"],
                ["C2", "Privacy Policy completa GDPR/IE", "Critico legale"],
                ["C3", "WhiteNoise + static produzione", "Critico deploy"],
                ["C4", "Password reset funzionante", "Critico UX/auth"],
                ["F1", "Account Settings (password/email/DoB)", "Backlog prodotto"],
                ["F2", "Directory membri /community/members/", "Backlog prodotto"],
                ["F3", "UI check-in attendance staff", "Backlog prodotto"],
                ["F4", "Email di moderazione all’utente", "Dipende da C1"],
                ["F5", "Form contatto (oltre Instagram)", "Opzionale"],
                ["F8", "SEO: OG, sitemap, robots", "Go-live"],
            ],
            styles,
            col_widths=[1.8 * cm, 9.2 * cm, 5.5 * cm],
        )
    )

    # 16
    story.append(Paragraph("16. Conclusioni e priorità pre-lancio", styles["h1"]))
    story.append(
        Paragraph(
            "JamSession Lab è già una piattaforma coerente e sostanzialmente completa sul piano del prodotto core: "
            "utenti, eventi, RSVP, gallery e community moderata. "
            "L’architettura a sei app è chiara e allineata allo scopo del sito.",
            styles["body"],
        )
    )
    story.append(
        Paragraph(
            "I collegamenti esterni operativi oggi sono tre pilastri: "
            "<b>Neon</b> (dati), <b>Cloudinary</b> (media), <b>CDN frontend</b> (Tailwind/Alpine/AOS/Fonts), "
            "più link sociali WhatsApp/Instagram e il repository GitHub. "
            "L’anello debole per il go-live pubblico è la posta elettronica reale e i task critici C1–C4.",
            styles["body"],
        )
    )
    story.append(Paragraph("Ordine consigliato verso il lancio", styles["h2"]))
    story.append(
        bullets(
            [
                "Fase 0: quick wins sicuri (piccoli bug UX/code smell).",
                "Fase 1: C1 SMTP · C2 Privacy · C3 WhiteNoise · C4 password reset.",
                "Fase 2: correzioni sicurezza/correttezza (token unique, validazioni upload, policy RSVP).",
                "Fase 3–4: performance e polish frontend.",
                "Fase 5–6: feature mancanti + SEO + dominio/HTTPS hardening.",
            ],
            styles,
        )
    )
    story.append(Spacer(1, 0.6 * cm))
    story.append(
        Paragraph(
            f"Documento generato automaticamente dall’analisi del codice del progetto — {date.today().isoformat()}. "
            "Non contiene secret, password o connection string reali.",
            styles["meta"],
        )
    )

    doc = SimpleDocTemplate(
        str(OUTPUT_PATH),
        pagesize=A4,
        leftMargin=1.8 * cm,
        rightMargin=1.8 * cm,
        topMargin=1.8 * cm,
        bottomMargin=1.8 * cm,
        title="JamSession Lab — Audit tecnico completo",
        author="JamSession Lab Audit",
    )
    doc.build(story, onFirstPage=add_header_footer, onLaterPages=add_header_footer)
    print(f"PDF scritto in: {OUTPUT_PATH}")


if __name__ == "__main__":
    build_document()
