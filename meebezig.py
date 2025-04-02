import pywikibot
from datetime import datetime, timedelta, timezone
import sys
import schedule
import time
import re

# Configuratie
SITE_CODE = 'nl'
FAMILY = 'wikipedia'
WEEK_THRESHOLD = 3
MEEBEZIG_SJABLOON_NAAM = 'meebezig'
OVERLEG_SJABLOON = 'MeebezigVerwijdermelding'
VERWIJDER_BEWERKINGSTEKST = 'Bot: sjabloon {{meebezig}} langer dan een dag aanwezig zonder recente bewerkingen.'
OPERATOR = "ItsNyoty"

def template_exists(text, template_name):
    template_name_with_space = template_name[:3] + ' ' + template_name[3:]  
    pattern = re.compile(r'\{\{\s*(' + template_name + r'|' + template_name.capitalize().replace(' ', '') + r'|' + template_name_with_space + r'|' + template_name_with_space.capitalize() + r')\s*(\|\s*.*?)?\}\}', re.IGNORECASE)
    return bool(pattern.search(text))

def check_meebezig_templates(edit_talk_page=False, remove_template=False, ignore_recent_edits=False):
    try:
        site = pywikibot.Site(SITE_CODE, FAMILY)
        meebezig_sjabloon = pywikibot.Page(site, 'Sjabloon:' + MEEBEZIG_SJABLOON_NAAM)
        pywikibot.output(f"Sjabloonpagina opgehaald: {meebezig_sjabloon.title()}")
        pages = meebezig_sjabloon.getReferences(namespaces=[0])
        pywikibot.output(f"Aantal verwijzende pagina's: {len(list(pages))}")
        pages = meebezig_sjabloon.getReferences(namespaces=[0])

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
                    pywikibot.output(f"Sjabloon {{meebezig}} gevonden op: {page.title()}")
                    add_date = None
                    last_edit_date = None
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

                    for rev in page.revisions(content=False, total=1):
                        timestamp_str = str(rev.timestamp)
                        if timestamp_str.endswith('Z'):
                            timestamp_str = timestamp_str[:-1] + '+00:00'
                        try:
                            last_edit_date = datetime.fromisoformat(timestamp_str)
                        except ValueError as e:
                            pywikibot.error(f"Kon last_edit_date niet parsen: {timestamp_str} - {e}")
                        break

                    if add_date and last_edit_date and meebezig_adder:
                        now = datetime.now(timezone.utc)
                        add_date_utc = add_date.replace(tzinfo=timezone.utc)
                        last_edit_date_utc = last_edit_date.replace(tzinfo=timezone.utc)

                        delta = now - add_date_utc
                        time_since_last_edit = now - last_edit_date_utc

                        if delta.days >= WEEK_THRESHOLD:
                            pywikibot.output(f"Sjabloon {{meebezig}} langer dan {WEEK_THRESHOLD} dagen op: {page.title()} (toegevoegd op {add_date_utc.strftime('%Y-%m-%d')}) door {meebezig_adder}")

                            if not ignore_recent_edits and time_since_last_edit < timedelta(days=3):
                                pywikibot.output(f"Pagina {page.title()} is recent bewerkt, wordt overgeslagen.")
                                continue  

                            try:
                                meebezig_adder_user = pywikibot.User(site, meebezig_adder)
                                talk_page = meebezig_adder_user.getUserTalkPage()
                                talk_text = talk_page.get()

                                melding = f"{{{{subst:{OVERLEG_SJABLOON}|gebruiker={meebezig_adder}|datum={add_date_utc.isoformat()}|artikel={page.title(as_link=True)}}}}}"

                                if melding not in talk_text:
                                    if edit_talk_page:
                                        pywikibot.output(f"Overlegpagina bewerken van {meebezig_adder}")
                                        talk_page.put(talk_text + '\n\n' + melding, f"Bot: Melding sjabloon {{meebezig}} op {page.title()}")
                                    else:
                                        pywikibot.output(f"Simuleer: Overlegpagina bewerken van {meebezig_adder}")
                                        pywikibot.output(f"Melding geplaatst op overlegpagina van {meebezig_adder}")
                                    pywikibot.output(f"Melding al aanwezig op overlegpagina van {meebezig_adder}")
                                else:
                                    pywikibot.output(f"Melding al aanwezig op overlegpagina van {meebezig_adder}")
                            except Exception as e:
                                pywikibot.error(f"Fout bij plaatsen overlegpaginabericht op {page.title()}: {e}")

                            if remove_template:
                                try:
                                    template_name_with_space = MEEBEZIG_SJABLOON_NAAM[:3] + ' ' + MEEBEZIG_SJABLOON_NAAM[3:]  # "meebezig" -> "mee bezig"
                                    pattern = r'\{\{\s*(' + MEEBEZIG_SJABLOON_NAAM + r'|' + MEEBEZIG_SJABLOON_NAAM.capitalize() + r'|' + template_name_with_space + r'|' + template_name_with_space.capitalize() + r')\s*(\|\s*.*?)?\}\}'
                                    new_text = re.sub(pattern, '', text, flags=re.IGNORECASE).strip()

                                    page.put(new_text, VERWIJDER_BEWERKINGSTEKST)
                                    pywikibot.output(f"Sjabloon {{meebezig}} verwijderd van: {page.title()}")
                                except Exception as e:
                                    pywikibot.error(f"Fout bij verwijderen sjabloon van {page.title()}: {e}")
                            else:
                                pywikibot.output(f"Simuleer: Sjabloon {{meebezig}} verwijderen van: {page.title()}")
                        else:
                            pywikibot.output(f"Sjabloon {{meebezig}} is niet langer dan {WEEK_THRESHOLD} dagen oud op: {page.title()}")
                else:
                    pywikibot.output(f"Sjabloon {{meebezig}} niet (meer) gevonden op: {page.title()}")

            except pywikibot.exceptions.IsRedirectPageError:
                pywikibot.output(f"{page.title()} is een redirect, wordt overgeslagen.")
            except pywikibot.exceptions.NoPageError:
                pywikibot.output(f"Pagina niet gevonden: {page.title()}")
            except Exception as e:
                pywikibot.error(f"Algemene fout bij verwerking van {page.title()}: {e}")

        return True

    except Exception as e:
        pywikibot.error(f"Algemene fout tijdens de run: {e}")
        return False

def send_notification(success):
    site = pywikibot.Site(SITE_CODE, FAMILY)
    user = pywikibot.User(site, OPERATOR)
    talk_page = user.getUserTalkPage()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if success:
        return

    else:
        message = f"Botrun uitgevoerd op {now} is mislukt. Zie de botlog voor details. ~~~~"

    talk_text = talk_page.get()
    notification = f"\n\n== Botrun rapport ({now}) ==\n{message}"

    try:
        talk_page.put(talk_text + notification, "Bot: Rapport van de botrun.")
        pywikibot.output(f"Melding geplaatst op overlegpagina van {OPERATOR}.")
    except Exception as e:
        pywikibot.error(f"Fout bij het plaatsen van de melding op de overlegpagina van {OPERATOR}: {e}")

def meebezig(edit_talk_page=True, remove_template=True, ignore_recent_edits=False):
    pywikibot.config.dry = not (edit_talk_page or remove_template)
    success = check_meebezig_templates(edit_talk_page, remove_template, ignore_recent_edits)
    send_notification(success)

def main():
    meebezig(edit_talk_page=True, remove_template=True, ignore_recent_edits=False)

    schedule.every().day.at("00:00").do(lambda: meebezig(edit_talk_page=True, remove_template=True, ignore_recent_edits=False))

    while True:
        schedule.run_pending()
        time.sleep(60)

if __name__ == '__main__':
    try:
        site = pywikibot.Site(SITE_CODE, FAMILY)
        user = pywikibot.User(site, OPERATOR)
        pywikibot.output(f"Bot draait als: {user.username()}")
    except Exception as e:
        pywikibot.error(f"Configuratie fout: {e}.  Zorg ervoor dat user-config.py correct is ingesteld.")
        sys.exit()

    pywikibot.config.dry = False  # TESTMODUS FALSE=UIT TRUE=AAN
    main()
