import pywikibot
from datetime import datetime, timedelta, timezone
import sys
import schedule
import time
import re

# Configuratie
SITE_CODE = 'nl'
FAMILY = 'wikipedia'
WEEK_THRESHOLD = 7
MEEBEZIG_SJABLOON_NAAM = 'meebezig'
OVERLEG_SJABLOON = 'MeebezigHerinnering'
OPERATOR = "ItsNyoty"
LOG_PAGE_TITLE = 'Gebruiker:Nyo\'s Helper/Meebezig/Logboek'

# Tabel-headers voor de logpagina
LOG_PAGE_HEADER = """{| class="wikitable sortable"
|+ Overzicht van <nowiki>{{meebezig}}</nowiki>-sjabloon gebruik. Afgehandelde items worden automatisch opgeruimd.
! Paginatitel
! Plaatser sjabloon
! Tijd van plaatsing
! Sjabloon verwijderaar
! Tijd van verwijdering
|-
"""
LOG_PAGE_FOOTER = "|}"

def template_exists(text, template_name):
    """Checks if a template with the given name exists in the text."""
    variations = [template_name.replace(' ', ''), template_name.capitalize().replace(' ', ''), template_name]
    pattern_str = r'\{\{\s*(' + r'|'.join(re.escape(name) for name in variations) + r')\s*(\|\s*.*?)?\}\}'
    pattern = re.compile(pattern_str, re.IGNORECASE)
    return bool(pattern.search(text))

def parse_iso_date(date_str: str | datetime) -> datetime | None:
    if not date_str or isinstance(date_str, datetime): return date_str
    try:
        if date_str.endswith('Z'): date_str = date_str[:-1] + '+00:00'
        dt = datetime.fromisoformat(date_str)
        if dt.tzinfo is None: return dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError): return None

def find_template_adder(page: pywikibot.Page, template_name: str) -> tuple[str | None, datetime | None]:
    """Finds the user and timestamp for the most recent addition of a template."""
    pywikibot.output(f"Nieuwe pagina: analyse van historie voor {page.title()}...")
    try:
        revisions = list(page.revisions(content=True))
        for i, current_rev in enumerate(revisions):
            current_has_template = template_exists(current_rev.text, template_name)
            parent_has_template = False
            if i + 1 < len(revisions):
                parent_rev = revisions[i + 1]
                parent_has_template = template_exists(parent_rev.text, template_name)
            
            if current_has_template and not parent_has_template:
                adder_user = current_rev.user
                add_timestamp = parse_iso_date(str(current_rev.timestamp))
                pywikibot.output(f"Plaatser gevonden: '{adder_user}' op {add_timestamp}")
                return adder_user, add_timestamp
    except Exception as e:
        pywikibot.error(f"Fout bij het analyseren van de historie van {page.title()}: {e}")
    return None, None

def check_meebezig_templates(edit_talk_page=False):
    pywikibot.output("check_meebezig_templates() gestart met herstelde logica")
    site = pywikibot.Site(SITE_CODE, FAMILY)
    site.login()
    bot_username = site.username() 
    
    log_page = pywikibot.Page(site, LOG_PAGE_TITLE)
    try:
        original_log_text = log_page.get()
        log_data = parse_log_page(original_log_text)
    except pywikibot.exceptions.NoPageError:
        original_log_text, log_data = "", {}

    meebezig_sjabloon = pywikibot.Page(site, 'Sjabloon:' + MEEBEZIG_SJABLOON_NAAM)
    current_pages_with_template = {p.title() for p in meebezig_sjabloon.getReferences(namespaces=[0])}

    pages_to_remove_from_log = []

    for page_title, data in list(log_data.items()):
        if page_title not in current_pages_with_template:
            if data.get('removed_by'):
                pywikibot.output(f"'{page_title}' is al afgehandeld, wordt opgeruimd.")
                pages_to_remove_from_log.append(page_title)
            else:
                pywikibot.output(f"Sjabloon is nieuw verwijderd van '{page_title}', wordt gelogd.")
                try:
                    page = pywikibot.Page(site, page_title)
                    last_rev = page.latest_revision
                    log_data[page_title]['removed_by'] = last_rev.user
                    log_data[page_title]['removed_at'] = parse_iso_date(str(last_rev.timestamp))
                except pywikibot.exceptions.NoPageError:
                    log_data[page_title]['removed_by'] = "Pagina verwijderd"
                    log_data[page_title]['removed_at'] = datetime.now(timezone.utc)
        else:
            add_date = parse_iso_date(data['added_at'])
            if add_date and (datetime.now(timezone.utc) - add_date).days >= WEEK_THRESHOLD:
                pywikibot.output(f"'{page_title}' staat al >{WEEK_THRESHOLD} dagen, herinnering wordt overwogen.")
                adder = data['added_by']
                try:
                    talk_page = pywikibot.User(site, adder).getUserTalkPage()
                    talk_text = talk_page.get(force=True) if talk_page.exists() else ""

                    deny_pattern = re.compile(r'\{\{\s*(?:Bots|Bot|NoBots)\s*\|[^}]*deny\s*=\s*([^}]*)\}\}', re.IGNORECASE)
                    is_denied = False
                    for match in deny_pattern.finditer(talk_text):
                        denied_list_str = match.group(1).lower()
                        denied_list = [b.strip() for b in denied_list_str.split(',')]
                        if 'all' in denied_list or bot_username.lower() in denied_list:
                            is_denied = True
                            break
                    
                    if is_denied:
                        pywikibot.output(f"Bot is uitgesloten op overlegpagina van {adder}. Melding wordt overgeslagen.")
                        continue 

                    melding = f"{{{{subst:{OVERLEG_SJABLOON}|artikel={page_title}}}}}"
                    check_string = f"[[{page_title}]]" 
                    
                    if check_string not in talk_text:
                        if edit_talk_page:
                            summary = f"Bot: Herinnering sjabloon {{meebezig}} op [[{page_title}]]"
                            talk_page.put(talk_text + '\n\n' + melding, summary)
                            pywikibot.output(f"Bericht geplaatst op OP van {adder}")
                        else:
                            pywikibot.output(f"DRY RUN: Bericht zou worden geplaatst op OP van {adder}")
                    else:
                        pywikibot.output(f"Herinnering voor {page_title} al aanwezig op OP van {adder}")

                except Exception as e:
                    pywikibot.error(f"Fout bij verwerken herinnering voor {page_title}: {e}")

    for page_title in pages_to_remove_from_log:
        if page_title in log_data:
            del log_data[page_title]

    for page_title in current_pages_with_template:
        if page_title not in log_data:
            page = pywikibot.Page(site, page_title)
            adder, add_date = find_template_adder(page, MEEBEZIG_SJABLOON_NAAM)
            if adder and add_date:
                log_data[page_title] = {
                    'added_by': adder, 'added_at': add_date,
                    'removed_by': None, 'removed_at': None
                }

    new_log_text = format_log_page(log_data)
    if new_log_text.strip() != original_log_text.strip():
        pywikibot.output("Logpagina wordt bijgewerkt.")
        log_page.put(new_log_text, "Bot: Bijwerken overzicht (nieuwe/verwijderde sjablonen en opruimen).")
    else:
        pywikibot.output("Geen wijzigingen in de logpagina.")

    pywikibot.output("check_meebezig_templates() voltooid.")

def parse_log_page(log_text):
    log_data = {}
    row_regex = re.compile(r'\|\s*\[\[(.*?)]]\s*\|\|\s*(.*?)\s*\|\|\s*(.*?)\s*\|\|\s*(.*?)\s*\|\|\s*(.*?)')
    for line in log_text.splitlines():
        if not line.startswith('| [['): continue
        match = row_regex.match(line)
        if match:
            try:
                page_title, added_by, added_at, removed_by, removed_at = [m.strip() for m in match.groups()]
                removed_at = removed_at.removesuffix('|-').strip()
                log_data[page_title] = {
                    'added_by': added_by, 'added_at': parse_iso_date(added_at),
                    'removed_by': removed_by if removed_by.lower() != 'n.v.t.' else None,
                    'removed_at': parse_iso_date(removed_at)
                }
            except Exception as e:
                pywikibot.error(f"Fout bij parsen van tabelrij: '{line}' - {e}")
    return log_data

def format_log_page(log_data):
    lines = [LOG_PAGE_HEADER]
    sorted_items = sorted(log_data.items(), key=lambda i: i[1].get('added_at') or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    
    for page_title, data in sorted_items:
        added_at_iso = data['added_at'].isoformat() if data.get('added_at') else 'N.v.t.'
        removed_at_iso = data['removed_at'].isoformat() if data.get('removed_at') else 'N.v.t.'
        
        lines.append(f"| [[{page_title}]] || {data.get('added_by') or 'Onbekend'} || {added_at_iso} || {data.get('removed_by') or 'N.v.t.'} || {removed_at_iso}")
        lines.append("|-")

    if lines and lines[-1] == "|-": lines.pop()
    lines.append(LOG_PAGE_FOOTER)
    return "\n".join(lines)


def meebezig(edit_talk_page=False):
    pywikibot.output("meebezig() gestart")
    pywikibot.config.dry = not edit_talk_page
    try:
        check_meebezig_templates(edit_talk_page)
        pywikibot.output("meebezig() voltooid")
    except Exception as e:
        pywikibot.error(f"Fout in meebezig(): {e}")

def main():
    def run_job():
        meebezig(edit_talk_page=True)
    
    pywikibot.output("Scheduler geïnitialiseerd...")
    schedule.every(1).hour.do(run_job)
    pywikibot.output("Eerste run bij opstarten.")
    run_job()
    
    while True:
        schedule.run_pending()
        time.sleep(60)

if __name__ == '__main__':
    try:
        site = pywikibot.Site(SITE_CODE, FAMILY)
        pywikibot.output(f"Bot draait als: {site.username()}")
    except Exception as e:
        pywikibot.error(f"Configuratie fout: {e}. Zorg voor user-config.py.")
        sys.exit()

    main()
