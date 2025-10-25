import pywikibot
from datetime import datetime, timedelta, timezone
import sys
import schedule
import time
import re
from collections import defaultdict

# Configuratie
SITE_CODE = 'nl'
FAMILY = 'wikipedia'
WEEK_THRESHOLD = 7
MEEBEZIG_SJABLOON_NAAM = 'meebezig'
OVERLEG_SJABLOON = 'MeebezigHerinnering'
OPERATOR = "ItsNyoty"
LOG_PAGE_TITLE = 'Gebruiker:Nyo\'s Helper/Meebezig/Logboek'

# Tabel-headers voor de logpagina (zoals gevraagd)
LOG_PAGE_HEADER = """{| class="wikitable sortable"
|+ Overzicht van <nowiki>{{meebezig}}</nowiki>-sjabloon gebruik
! Paginatitel
! Plaatser sjabloon
! Tijd van plaatsing
! Sjabloon verwijderaar
! Tijd van verwijdering
|-
"""
LOG_PAGE_FOOTER = "|}"


def template_exists(text, template_name):
    """
    Checks if a template with the given name exists in the text.
    Handles case-insensitivity and variations with spaces.
    """
    template_name_with_space = template_name[:3] + ' ' + template_name[3:]
    pattern = re.compile(r'\{\{\s*(' + template_name + r'|' + template_name.capitalize().replace(' ', '') + r'|' + template_name_with_space + r'|' + template_name_with_space.capitalize() + r')\s*(\|\s*.*?)?\}\}', re.IGNORECASE)
    return bool(pattern.search(text))

def check_meebezig_templates(edit_talk_page=False):
    """
    Checks pages using the "meebezig" template and notifies the user if it's been there for a week.
    """
    pywikibot.output("check_meebezig_templates() gestart")  # DEBUG

    try:
        site = pywikibot.Site(SITE_CODE, FAMILY)
        pywikibot.output("Aanmelden...")
        site.login()
        pywikibot.output("Aanmelden voltooid.")
        meebezig_sjabloon = pywikibot.Page(site, 'Sjabloon:' + MEEBEZIG_SJABLOON_NAAM)
        pywikibot.output(f"Sjabloonpagina opgehaald: {meebezig_sjabloon.title()}")

        bot_username = site.username()

        log_page = pywikibot.Page(site, LOG_PAGE_TITLE)
        try:
            log_text = log_page.get()
            log_data = parse_log_page(log_text)
            pywikibot.output(f"{len(log_data)} items geparsed uit logboek.")
        except pywikibot.exceptions.NoPageError:
            pywikibot.output(f"Logpagina {LOG_PAGE_TITLE} bestaat niet, wordt aangemaakt.")
            log_text = ""
            log_data = {}
        except Exception as e:
            pywikibot.error(f"Fout bij parsen logpagina (kan tabel-format zijn): {e}. Log wordt gereset.")
            log_text = "" # Reset bij parse-fout
            log_data = {}


        pages = meebezig_sjabloon.getReferences(namespaces=[0])
        pages = list(pages)
        pywikibot.output(f"Aantal verwijzende pagina's: {len(pages)}")

        for page in pages:
            pywikibot.output(f"Verwerking pagina: {page.title()}")

            if page.namespace() == 2:
                pywikibot.output(f"Gebruikerspagina overgeslagen: {page.title()}")
                continue

            try:
                page.purge()
                text = page.get()
                pywikibot.output(f"Pagina inhoud opgehaald: {page.title()}")

                if template_exists(text, MEEBEZIG_SJABLOON_NAAM):
                    page_title = page.title()
                    add_date = None
                    meebezig_adder = None

                    for rev in page.revisions(content=True):
                        if template_exists(rev.text, MEEBEZIG_SJABLOON_NAAM):
                            timestamp_str = str(rev.timestamp)
                            if timestamp_str.endswith('Z'):
                                timestamp_str = timestamp_str[:-1] + '+00:00'
                            try:
                                add_date = datetime.fromisoformat(timestamp_str)
                            except ValueError as e:
                                pywikibot.error(f"Kon add_date niet parsen: {timestamp_str} - {e}")
                            meebezig_adder = rev.user
                            pywikibot.output(f"Gebruiker die {{meebezig}} heeft toegevoegd: {meebezig_adder}")
                            break

                    if add_date and meebezig_adder:
                        now = datetime.now(timezone.utc)
                        add_date_utc = add_date.replace(tzinfo=timezone.utc)
                        delta = now - add_date_utc

                        if delta.days >= WEEK_THRESHOLD:
                            try:
                                meebezig_adder_user = pywikibot.User(site, meebezig_adder)
                                talk_page = meebezig_adder_user.getUserTalkPage()
                                talk_text = ""

                                # Voorkom cache: purge de overlegpagina voordat we de inhoud ophalen
                                try:
                                    talk_page.purge()
                                    talk_text = talk_page.get()
                                except pywikibot.exceptions.NoPageError:
                                    talk_text = "" # Pagina bestaat nog niet, dat is prima
                                except Exception as e:
                                    pywikibot.error(f"Kon overlegpagina {talk_page.title()} niet ophalen/purgen: {e}")
                                    continue # Ga naar de volgende pagina

                                # Compileer regex om {{Bots|...}} te vinden
                                deny_pattern = re.compile(r'\{\{\s*(?:Bots|Bot|NoBots)\s*\|[^}]*deny\s*=\s*([^}]*)\}\}', re.IGNORECASE)
                                is_denied = False
                                for match in deny_pattern.finditer(talk_text):
                                    denied_list_str = match.group(1).lower()
                                    denied_list = [b.strip() for b in denied_list_str.split(',')]
                                    if 'all' in denied_list or bot_username.lower() in denied_list:
                                        is_denied = True
                                        break
                                
                                if is_denied:
                                    pywikibot.output(f"Bot is uitgesloten op overlegpagina van {meebezig_adder}. Melding wordt overgeslagen.")
                                else:
                                    melding = f"{{{{subst:{OVERLEG_SJABLOON}|artikel={page.title(as_link=True)}}}}}"
                                    
                                    check_string = page.title(as_link=True)
                                    
                                    if check_string not in talk_text:
                                        if edit_talk_page:
                                            pywikibot.output(f"Overlegpagina bewerken van {meebezig_adder} voor {check_string}")
                                            talk_page.put(talk_text + '\n\n' + melding, f"Bot: Herinnering sjabloon {{meebezig}} op {page.title()}")
                                        else:
                                            pywikibot.output(f"Simuleer: Overlegpagina bewerken van {meebezig_adder}")
                                            pywikibot.output(f"Melding geplaatst op overlegpagina van {meebezig_adder}")
                                    else:
                                        pywikibot.output(f"Herinnering voor {check_string} al aanwezig op overlegpagina van {meebezig_adder}")
                            
                            except Exception as e:
                                pywikibot.error(f"Fout bij plaatsen overlegpaginabericht op {page.title()}: {e}")
                        
                        if page_title not in log_data:
                            pywikibot.output(f"Nieuwe {{meebezig}} op {page_title}")

                            log_data[page_title] = {
                                'added_by': meebezig_adder,
                                'added_at': add_date.isoformat(),
                                'removed_by': None,
                                'removed_at': None
                            }
                        else:
                            pywikibot.output(f"{{meebezig}} op {page_title} al bekend.")

            except pywikibot.exceptions.IsRedirectPageError:
                pywikibot.output(f"{page.title()} is een redirect, wordt overgeslagen.")
            except pywikibot.exceptions.NoPageError:
                pywikibot.output(f"Pagina niet gevonden: {page.title()}")
            except Exception as e:
                pywikibot.error(f"Algemene fout bij verwerking van {page.title()}: {e}")

        pywikibot.output("Start tweede pas")

        pages_in_log = list(log_data.keys())

        for page_title in pages_in_log:
            pywikibot.output(f"Controleren van {page_title} op verwijdering")
            try:
                page = pywikibot.Page(site, page_title)
                page.purge()
                text = page.get()

                if not template_exists(text, MEEBEZIG_SJABLOON_NAAM):
                    if log_data[page_title]['removed_by'] is None:
                        pywikibot.output(f"{{meebezig}} is verwijderd van {page_title}")

                        remover = None
                        remove_date = None

                        for rev in page.revisions(content=False, total=2):
                            remover = rev.user
                            remove_timestamp_str = str(rev.timestamp)
                            if remove_timestamp_str.endswith('Z'):
                                remove_timestamp_str = remove_timestamp_str[:-1] + '+00:00'
                            try:
                                remove_date = datetime.fromisoformat(remove_timestamp_str)
                            except ValueError as e:
                                pywikibot.error(f"Kon remove_date niet parsen: {remove_timestamp_str} - {e}")
                            break

                        if remove_date is None:
                            remove_date = datetime.now(timezone.utc)

                        log_data[page_title]['removed_by'] = remover
                        log_data[page_title]['removed_at'] = remove_date.isoformat()

                    else:
                        pywikibot.output(f"{{meebezig}} verwijdering van {page_title} al bekend.")

                else:
                     pywikibot.output(f"{{meebezig}} nog steeds aanwezig op {page_title}")

            except pywikibot.exceptions.NoPageError:
                 pywikibot.output(f"Pagina {page_title} niet gevonden (mogelijk verwijderd).  Verwijderen uit de log.")
                 if page_title in log_data:
                    del log_data[page_title]
            except Exception as e:
                pywikibot.error(f"Fout bij controleren van {page_title}: {e}")
                continue

        new_log_text = format_log_page(log_data)
        
        if new_log_text.strip() != log_text.strip():
            pywikibot.output("Logpagina wordt bijgewerkt.")
            try:
                log_page.put(new_log_text, "Bot: Bijwerken overzicht van {{meebezig}}-sjabloon gebruik (tabel-format).")
                log_updated = True
            except Exception as e:
                pywikibot.error(f"Fout bij schrijven naar logpagina: {e}")
                log_updated = False
        else:
            pywikibot.output("Geen wijzigingen in de logpagina.")
            log_updated = False

        pywikibot.output("check_meebezig_templates() voltooid")  # DEBUG
        return log_updated

    except Exception as e:
        pywikibot.error(f"Algemene fout tijdens de run: {e}")
        pywikibot.output("check_meebezig_templates() afgebroken met fout")  # DEBUG
        return False

def parse_log_page(log_text):
    """
    Parses the log page wikitext table into a dictionary.
    """
    log_data = {}
    lines = log_text.splitlines()
    
    # Regex om een tabelrij te matchen
    # | [[Artikelnaam]] || Gebruiker || 2024-01-01T... || Gebruiker2 || 2024-01-02T...
    # Maakt || optioneel voor flexibiliteit
    row_regex = re.compile(r'\|\s*\[\[(.*?)]]\s*\|\|?\s*(.*?)\s*\|\|?\s*(.*?)\s*\|\|?\s*(.*?)\s*\|\|?\s*(.*?)\s*')

    for line in lines:
        if not line.startswith('| '):
            continue # Sla headers, comments, etc. over (alles wat niet met '| ' begint)

        match = row_regex.match(line)
        if match:
            try:
                page_title = match.group(1).strip()
                added_by = match.group(2).strip()
                added_at = match.group(3).strip()
                removed_by = match.group(4).strip()
                removed_at = match.group(5).strip()

                log_data[page_title] = {
                    'added_by': added_by,
                    'added_at': added_at,
                    'removed_by': removed_by if removed_by.lower() != 'n.v.t.' else None,
                    'removed_at': removed_at if removed_at.lower() != 'n.v.t.' else None
                }
            except Exception as e:
                pywikibot.error(f"Fout bij parsen van tabelrij: {line} - {e}")
                continue
                
    return log_data

def format_log_page(log_data):
    """
    Formats the log data into the log page wikitext table.
    """
    lines = [LOG_PAGE_HEADER]
    
    sorted_page_titles = sorted(log_data.keys())
    
    for page_title in sorted_page_titles:
        data = log_data[page_title]
        added_by = data['added_by']
        added_at = data['added_at']
        removed_by = data['removed_by'] if data['removed_by'] else 'N.v.t.'
        removed_at = data['removed_at'] if data['removed_at'] else 'N.v.t.'

        # Maak de tabelrij
        # | [[Paginatitel]] || Plaatser || Tijd || Verwijderaar || Tijd
        lines.append(f"| [[{page_title}]] || {added_by} || {added_at} || {removed_by} || {removed_at}")
        lines.append("|-") 

    if len(lines) > 1 and lines[-1] == "|-":
        lines.pop()
        
    lines.append(LOG_PAGE_FOOTER)
    return "\n".join(lines)


def meebezig(edit_talk_page=False):
    """
    Main function to run the meebezig bot.
    """
    pywikibot.output("meebezig() gestart")  # DEBUG
    pywikibot.config.dry = not (edit_talk_page)
    try:
        log_updated = check_meebezig_templates(edit_talk_page)
        pywikibot.output(f"meebezig() voltooid, log_updated: {log_updated}")  # DEBUG
        return log_updated
    except Exception as e:
        pywikibot.error(f"Fout in meebezig(): {e}")
        pywikibot.output("meebezig() afgebroken met fout")  # DEBUG
        return False


def main():
    """
    Main entry point of the script.
    """

    def run_meebezig():
        meebezig(edit_talk_page=True)

    pywikibot.output("Scheduler wordt geinitialiseerd...")

    schedule.every(30).seconds.do(run_meebezig)

    pywikibot.output("Eerste run van meebezig")
    meebezig(edit_talk_page=True)

    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == '__main__':
    try:
        site = pywikibot.Site(SITE_CODE, FAMILY)
        user = pywikibot.User(site, OPERATOR)
        pywikibot.output(f"Bot draait als: {user.username()}")
    except Exception as e:
        pywikibot.error(f"Configuratie fout: {e}.  Zorg ervoor dat user-config.py correct is ingesteld.")
        sys.exit()

    # pywikibot.config.dry = False 
    main()
