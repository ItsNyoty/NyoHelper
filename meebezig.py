import pywikibot
from datetime import datetime, timedelta, timezone

# Configuratie
SITE_CODE = 'nl'
FAMILY = 'wikipedia'
WEEK_THRESHOLD = 7
MEEBEZIG_SJABLOON_NAAM = 'meebezig'
OVERLEG_TEKST = """{{subst:MeebezigMelding|%s}}"""
VERWIJDER_BEWERKINGSTEKST = 'Bot: sjabloon {{meebezig}} langer dan een week aanwezig zonder recente bewerkingen.'
OPERATOR = "ItsNyoty" #MELDING

def check_meebezig_templates():
    try:
        site = pywikibot.Site(SITE_CODE, FAMILY)
        meebezig_sjabloon = pywikibot.Page(site, 'Sjabloon:' + MEEBEZIG_SJABLOON_NAAM)
        pages = meebezig_sjabloon.getReferences(namespaces=[0])

        for page in pages:
            if page.namespace() == 2:
                pywikibot.output(f"Gebruikerspagina overgeslagen: {page.title()}")
                continue

            try:
                text = page.get()
                if '{{' + MEEBEZIG_SJABLOON_NAAM + '}}' in text or '{{' + MEEBEZIG_SJABLOON_NAAM.capitalize() + '}}' in text:
                    add_date = None
                    last_edit_date = None

                    for rev in page.revisions(reverse=True, content=True):
                        if '{{' + MEEBEZIG_SJABLOON_NAAM + '}}' in rev.text or '{{' + MEEBEZIG_SJABLOON_NAAM.capitalize() + '}}' in rev.text:
                            try:
                                add_date = rev.timestamp.datetime()
                            except:
                                add_date = datetime.fromisoformat(str(rev.timestamp))
                            break

                    for rev in page.revisions(content=False, total=1):
                        try:
                            last_edit_date = rev.timestamp.datetime()
                        except:
                            last_edit_date = datetime.fromisoformat(str(rev.timestamp))
                        break

                    if add_date and last_edit_date:
                        now = datetime.now(timezone.utc)
                        add_date_utc = add_date.replace(tzinfo=timezone.utc)
                        last_edit_date_utc = last_edit_date.replace(tzinfo=timezone.utc)

                        delta = now - add_date_utc
                        time_since_last_edit = now - last_edit_date_utc

                        if time_since_last_edit < timedelta(weeks=1):
                            pywikibot.output(f"Pagina {page.title()} is recent bewerkt, wordt overgeslagen.")
                            continue

                        if delta.days >= WEEK_THRESHOLD:
                            pywikibot.output(f"Sjabloon {{meebezig}} langer dan {WEEK_THRESHOLD} dagen op: {page.title()} (toegevoegd op {add_date.strftime('%Y-%m-%d')})")

                            try:
                                first_contributor = next(page.revisions(reverse=True, user=True))
                                talk_page = first_contributor.user().talk_page()
                                talk_text = talk_page.get()
                                melding = OVERLEG_TEKST % (page.title(as_link=True))
                                if melding not in talk_text:
                                    talk_page.put(talk_text + '\n\n' + melding, f"Bot: Melding sjabloon {{meebezig}} op {page.title()}")
                                    pywikibot.output(f"Melding geplaatst op overlegpagina van {first_contributor.user().username()}")
                                else:
                                    pywikibot.output(f"Melding al aanwezig op overlegpagina van {first_contributor.user().username()}")
                            except Exception as e:
                                pywikibot.error(f"Fout bij plaatsen overlegpaginabericht op {page.title()}: {e}")

                            try:
                                new_text = text.replace('{{' + MEEBEZIG_SJABLOON_NAAM + '}}', '').replace('{{' + MEEBEZIG_SJABLOON_NAAM.capitalize() + '}}', '').strip()
                                page.put(new_text, VERWIJDER_BEWERKINGSTEKST)
                                pywikibot.output(f"Sjabloon {{meebezig}} verwijderd van: {page.title()}")
                            except Exception as e:
                                pywikibot.error(f"Fout bij verwijderen sjabloon van {page.title()}: {e}")
                        else:
                            pywikibot.output(f"Datum van toevoegen van {{meebezig}} niet gevonden op: {page.title()}")
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
        message = f"Botrun uitgevoerd op {now}, maar er zijn fouten opgetreden. Zie de botlog voor details. ~~~~"
        
    talk_text = talk_page.get()
    notification = f"\n\n== Botrun rapport ({now}) ==\n{message}"

    try:
        talk_page.put(talk_text + notification, "Bot: Rapport van de botrun.")
        pywikibot.output(f"Melding geplaatst op overlegpagina van {OPERATOR}.")
    except Exception as e:
        pywikibot.error(f"Fout bij het plaatsen van de melding op de overlegpagina van {OPERATOR}: {e}")

def meebezig():
    success = check_meebezig_templates()
    send_notification(success)
