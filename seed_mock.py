"""Seed de database met mock data voor Van der Valk Hotel Ridderkerk."""

from app import app
from models import (db, Organisatie, Gebruiker, Menu, Gerecht, MenuSegment,
                    TrendAnalyse, TrendGeheugen, TrendConfig, MenuAnnotatie)
from datetime import datetime, timezone


# ── Ingrediënten per gerecht (naam, categorie, hoeveelheid, eenheid) ──
# categorie: vers | droog | diepvries | saus | zuivel
# eenheid: g | ml | stuk | el | tl | portie
INGREDIENTEN = {
    # --- VOORGERECHTEN ---
    "Poké Bowl": [
        ("sushirijst", "droog", 150, "g"), ("mango", "vers", 0.5, "stuk"), ("wakame", "droog", 10, "g"),
        ("sojabonen", "vers", 40, "g"), ("avocado", "vers", 0.5, "stuk"), ("wortel", "vers", 50, "g"),
        ("zeewierchips", "droog", 10, "g"), ("sesam-sojadressing", "saus", 30, "ml"),
    ],
    "Seizoenssalade": [
        ("pompoen", "vers", 80, "g"), ("gele winterpeen", "vers", 60, "g"), ("rozijnen", "droog", 15, "g"),
        ("bonen", "vers", 50, "g"), ("bladpeterselie", "vers", 5, "g"), ("kruidendressing", "saus", 30, "ml"),
    ],
    "Burrata": [
        ("burrata", "zuivel", 125, "g"), ("perzik", "vers", 0.5, "stuk"), ("serranoham", "vers", 40, "g"),
        ("rucola", "vers", 20, "g"), ("tomaat", "vers", 80, "g"), ("basilicum", "vers", 5, "g"),
        ("aceto-stroop", "saus", 15, "ml"),
    ],
    "Gerookte Zalm": [
        ("gerookte zalm", "vers", 80, "g"), ("bosui", "vers", 15, "g"), ("rettich", "vers", 20, "g"),
        ("sesam-sojadressing", "saus", 20, "ml"), ("japanse mayonaise", "saus", 15, "ml"),
    ],
    "Carpaccio": [
        ("rundercarpaccio", "vers", 80, "g"), ("parmezaanse kaas", "zuivel", 20, "g"),
        ("bieslook", "vers", 5, "g"), ("spek", "vers", 15, "g"), ("pijnboompitten", "droog", 10, "g"),
        ("truffelmayonaise", "saus", 20, "ml"),
    ],
    "Vitello Tonnato": [
        ("kalfsmuis", "vers", 100, "g"), ("tonijnmayonaise", "saus", 40, "ml"),
        ("kapperappels", "droog", 10, "g"), ("rucola", "vers", 15, "g"),
    ],
    "Caesarsalade": [
        ("romeinse sla", "vers", 100, "g"), ("caesardressing", "saus", 30, "ml"),
        ("parmezaanse kaas", "zuivel", 20, "g"), ("cherrytomaat", "vers", 60, "g"),
        ("rode ui", "vers", 20, "g"), ("croutons", "droog", 20, "g"), ("ei", "vers", 1, "stuk"),
    ],
    "Salade Geitenkaas": [
        ("babyleaf", "vers", 60, "g"), ("komkommer", "vers", 50, "g"), ("cherrytomaat", "vers", 50, "g"),
        ("bosbessen", "vers", 20, "g"), ("peer", "vers", 0.5, "stuk"), ("walnoten", "droog", 15, "g"),
        ("honingkruidendressing", "saus", 30, "ml"),
    ],
    "Ham & Meloen": [
        ("serranoham", "vers", 50, "g"), ("meloen", "vers", 150, "g"),
        ("granaatappel", "vers", 30, "g"), ("pijnboompitten", "droog", 10, "g"),
    ],
    "Iberico": [
        ("iberico", "vers", 60, "g"), ("gamba", "vers", 60, "g"), ("aioli", "saus", 20, "ml"),
        ("antiboise", "saus", 20, "ml"), ("parmezaanse kaas", "zuivel", 15, "g"),
    ],
    "Vispalet": [
        ("zalm", "vers", 50, "g"), ("krab", "vers", 40, "g"), ("gamba", "vers", 50, "g"),
        ("aardappel", "vers", 80, "g"), ("bieslook", "vers", 5, "g"), ("kerriedressing", "saus", 25, "ml"),
    ],
    "Cobb Salade": [
        ("little gem", "vers", 80, "g"), ("tomaat", "vers", 80, "g"), ("avocado", "vers", 0.5, "stuk"),
        ("rode ui", "vers", 20, "g"), ("ei", "vers", 1, "stuk"), ("spek", "vers", 30, "g"),
        ("ranchdressing", "saus", 30, "ml"),
    ],
    "Tonijn": [
        ("tonijn", "vers", 80, "g"), ("citrusmayonaise", "saus", 20, "ml"),
        ("zeewierchips", "droog", 10, "g"), ("sesamzaad", "droog", 5, "g"), ("wasabikruim", "droog", 5, "g"),
    ],
    "Tomatensoep": [
        ("tomaat", "vers", 200, "g"), ("room", "zuivel", 30, "ml"), ("ui", "vers", 40, "g"),
        ("knoflook", "vers", 5, "g"), ("olijfolie", "droog", 10, "ml"),
    ],
    "Bisque": [
        ("kreeft", "vers", 80, "g"), ("room", "zuivel", 50, "ml"), ("ui", "vers", 40, "g"),
        ("wortel", "vers", 30, "g"), ("selderij", "vers", 25, "g"), ("cognac", "droog", 15, "ml"),
    ],
    # --- VIS ---
    "Zalm": [
        ("zalm", "vers", 160, "g"), ("seizoensgroenten", "vers", 120, "g"),
        ("aardappel", "vers", 150, "g"), ("hollandaisesaus", "saus", 40, "ml"),
    ],
    "Pad Thai met Gamba": [
        ("rijstnoedels", "droog", 150, "g"), ("gamba", "vers", 120, "g"), ("knoflook", "vers", 5, "g"),
        ("bosui", "vers", 20, "g"), ("cashewnoten", "droog", 15, "g"), ("taug\u00e9", "vers", 40, "g"),
        ("rode peper", "vers", 5, "g"), ("limoen", "vers", 0.5, "stuk"),
    ],
    "Tongschar": [
        ("tongschar", "vers", 180, "g"), ("rivierkreeftjes", "vers", 60, "g"), ("prei", "vers", 50, "g"),
        ("aardappel", "vers", 150, "g"), ("roomboter", "zuivel", 20, "g"), ("zalmkuit", "vers", 10, "g"),
    ],
    "Heilbot": [
        ("heilbot", "vers", 160, "g"), ("polenta", "droog", 80, "g"), ("paddenstoelen", "vers", 60, "g"),
        ("rode wijn", "droog", 30, "ml"), ("jus", "saus", 40, "ml"),
    ],
    "Schelvis": [
        ("schelvis", "vers", 160, "g"), ("courgette", "vers", 60, "g"), ("paprika", "vers", 50, "g"),
        ("aubergine", "vers", 60, "g"), ("tomaat", "vers", 80, "g"),
        ("tomatentapenade", "saus", 20, "ml"), ("roseval aardappel", "vers", 120, "g"),
    ],
    "Sliptongen": [
        ("sliptong", "vers", 200, "g"), ("wortel", "vers", 60, "g"), ("aardappel", "vers", 150, "g"),
        ("peterselie", "vers", 5, "g"), ("roomboter", "zuivel", 20, "g"), ("citroen", "vers", 0.5, "stuk"),
    ],
    # --- VEGAN / VEGETARISCH ---
    "Spaghetti Bolognese": [
        ("spaghetti", "droog", 150, "g"), ("vegan gehakt", "vers", 100, "g"), ("tomaat", "vers", 120, "g"),
        ("ui", "vers", 40, "g"), ("knoflook", "vers", 5, "g"), ("olijfolie", "droog", 10, "ml"),
    ],
    "Rigatoni Cacio e Pepe": [
        ("rigatoni", "droog", 150, "g"), ("parmezaanse kaas", "zuivel", 30, "g"),
        ("pecorino", "zuivel", 20, "g"), ("zwarte peper", "droog", 2, "g"),
        ("roomboter", "zuivel", 25, "g"), ("peterselie", "vers", 5, "g"),
    ],
    "Groente Tajine": [
        ("couscous", "droog", 120, "g"), ("zoete aardappel", "vers", 100, "g"),
        ("kikkererwten", "droog", 60, "g"), ("rozijnen", "droog", 15, "g"),
        ("koriander", "vers", 5, "g"), ("olijven", "droog", 20, "g"), ("ras el hanout", "droog", 3, "g"),
    ],
    "Risotto": [
        ("risottorijst", "droog", 120, "g"), ("peer", "vers", 0.5, "stuk"),
        ("gorgonzola", "zuivel", 30, "g"), ("walnoten", "droog", 15, "g"),
        ("roomboter", "zuivel", 20, "g"),
    ],
    "'Geen Kip' Sat\u00e9": [
        ("plantaardige kip", "vers", 120, "g"), ("sat\u00e9saus", "saus", 40, "ml"),
        ("nasi", "droog", 150, "g"), ("komkommer", "vers", 50, "g"),
        ("cassavekroepoek", "droog", 15, "g"), ("krokante uitjes", "droog", 10, "g"),
    ],
    # --- VLEES ---
    "Tournedos": [
        ("ossenhaas", "vers", 180, "g"), ("seizoensgroenten", "vers", 120, "g"),
        ("aardappel", "vers", 150, "g"), ("jus", "saus", 40, "ml"),
    ],
    "Tournedos Speciaal": [
        ("ossenhaas", "vers", 180, "g"), ("ui", "vers", 40, "g"), ("spek", "vers", 30, "g"),
        ("champignon", "vers", 60, "g"), ("jus", "saus", 40, "ml"),
    ],
    "Oosterse Kipsat\u00e9": [
        ("kipfilet", "vers", 150, "g"), ("sat\u00e9saus", "saus", 40, "ml"), ("nasi", "droog", 150, "g"),
        ("komkommer", "vers", 50, "g"), ("kroepoek", "droog", 15, "g"),
        ("krokante uitjes", "droog", 10, "g"),
    ],
    "Varkenshaas": [
        ("varkenshaas", "vers", 160, "g"), ("seizoensgroenten", "vers", 120, "g"),
        ("aardappel", "vers", 150, "g"), ("jus", "saus", 40, "ml"),
    ],
    "Varkenshaas Speciaal": [
        ("varkenshaas", "vers", 160, "g"), ("ui", "vers", 40, "g"), ("spek", "vers", 30, "g"),
        ("champignon", "vers", 60, "g"), ("jus", "saus", 40, "ml"),
    ],
    "Cordon Bleu van Kipfilet": [
        ("kipfilet", "vers", 180, "g"), ("ham", "vers", 30, "g"), ("kaas", "zuivel", 30, "g"),
        ("paneermeel", "droog", 20, "g"), ("seizoensgroenten", "vers", 120, "g"),
        ("aardappel", "vers", 150, "g"),
    ],
    "Varkensschnitzel": [
        ("varkensschnitzel", "vers", 200, "g"), ("paneermeel", "droog", 25, "g"),
        ("seizoensgroenten", "vers", 120, "g"), ("aardappel", "vers", 150, "g"),
    ],
    "Varkensschnitzel Speciaal": [
        ("varkensschnitzel", "vers", 200, "g"), ("paneermeel", "droog", 25, "g"),
        ("ui", "vers", 40, "g"), ("spek", "vers", 30, "g"), ("champignon", "vers", 60, "g"),
    ],
    "Runder Ribeye 350 gram": [
        ("runder ribeye", "vers", 350, "g"), ("bloemkool", "vers", 100, "g"), ("ui", "vers", 40, "g"),
        ("krielaardappel", "vers", 150, "g"), ("cowboy butter", "saus", 25, "ml"),
    ],
    "Pluma Iberico": [
        ("ibericoschouder", "vers", 180, "g"), ("roseval aardappel", "vers", 120, "g"),
        ("groene asperge", "vers", 80, "g"), ("mango", "vers", 0.5, "stuk"),
        ("habanero", "vers", 5, "g"), ("mango-habanero salsa", "saus", 30, "ml"),
    ],
    "Angus Shortrib": [
        ("rundershortrib", "vers", 250, "g"), ("aardappel", "vers", 150, "g"),
        ("paddenstoelen", "vers", 60, "g"), ("rode wijn", "droog", 30, "ml"), ("jus", "saus", 40, "ml"),
    ],
    # --- NAGERECHTEN ---
    "Heisse Liebe": [
        ("vanille-ijs", "diepvries", 2, "portie"), ("frambozensaus", "saus", 30, "ml"),
        ("slagroom", "zuivel", 30, "ml"),
    ],
    "Dame Blanche": [
        ("vanille-ijs", "diepvries", 2, "portie"), ("witte chocolade", "droog", 20, "g"),
        ("chocoladesaus", "saus", 30, "ml"), ("crumble", "droog", 15, "g"),
        ("slagroom", "zuivel", 30, "ml"),
    ],
    "Bananensplit": [
        ("karamelijs", "diepvries", 1, "portie"), ("bananenijs", "diepvries", 1, "portie"),
        ("banaan", "vers", 1, "stuk"), ("karamelsaus", "saus", 30, "ml"),
        ("slagroom", "zuivel", 30, "ml"),
    ],
    "Fudge Brownie": [
        ("chocolade brownie", "droog", 1, "stuk"), ("notenspread", "droog", 20, "g"),
        ("karamel-zeezoutsaus", "saus", 25, "ml"), ("oreo", "droog", 2, "stuk"),
    ],
    "Stoofpeer Sorbet": [
        ("stoofpeer", "vers", 1, "stuk"), ("kaneelijs", "diepvries", 1, "portie"),
        ("stoofpeerijs", "diepvries", 1, "portie"), ("slagroom", "zuivel", 30, "ml"),
    ],
    "Proeverij van Sue Rotterdam": [
        ("choco-pistache bonbon", "droog", 2, "stuk"), ("stroopwafel", "droog", 1, "stuk"),
        ("lavendel-citroencrème", "saus", 30, "ml"), ("flower bite", "droog", 1, "stuk"),
    ],
    "Klassieke Tiramisu": [
        ("lange vingers", "droog", 4, "stuk"), ("espresso", "droog", 30, "ml"),
        ("cacao", "droog", 5, "g"), ("mascarpone", "zuivel", 80, "g"),
        ("kahl\u00faa", "droog", 15, "ml"),
    ],
    "Kaasplateau": [
        ("kaasplankje", "zuivel", 120, "g"), ("appel-peercompote", "saus", 30, "ml"),
        ("kletzenbrood", "droog", 2, "stuk"), ("druiven", "vers", 40, "g"),
    ],
    "Dubai Chocolade Dessert": [
        ("chocolade", "droog", 40, "g"), ("pistache", "droog", 15, "g"), ("kataifi", "droog", 20, "g"),
        ("witte chocolade", "droog", 20, "g"), ("chocolade-ijs", "diepvries", 1, "portie"),
    ],
    "Cr\u00e8me Br\u00fbl\u00e9e": [
        ("room", "zuivel", 120, "ml"), ("ei", "vers", 2, "stuk"), ("vanille", "droog", 3, "g"),
        ("suiker", "droog", 25, "g"),
    ],
}


def reset_and_seed():
    with app.app_context():
        # Alles verwijderen
        MenuAnnotatie.query.delete()
        Gerecht.query.delete()
        Menu.query.delete()
        TrendAnalyse.query.delete()
        TrendGeheugen.query.delete()
        TrendConfig.query.delete()
        MenuSegment.query.delete()
        Gebruiker.query.delete()
        Organisatie.query.delete()
        db.session.commit()
        print("Database geleegd.")

        # ── 1. Organisatie ──
        org = Organisatie(
            naam="Van der Valk Hotel Ridderkerk",
            adres="Krommeweg 1, 2988 EB Ridderkerk",
            website_url="https://www.hotelridderkerk.nl",
            beschrijving="Van der Valk Hotel Ridderkerk, nabij Rotterdam. Modern hotel-restaurant met een breed internationaal menu dat klassieke Van der Valk-gerechten combineert met Aziatische fusion en eigentijdse trends.",
            status="actief"
        )
        db.session.add(org)
        db.session.flush()

        # ── 2. Gebruiker ──
        user = Gebruiker(
            organisatie_id=org.id,
            naam="William Kraaijeveld",
            email="william.kraaijeveld@nohou.nl",
            rol="admin"
        )
        user.set_wachtwoord("test0000")
        db.session.add(user)
        db.session.flush()

        # ── 3. MenuSegment ──
        segment = MenuSegment(
            organisatie_id=org.id,
            goedgekeurd_door=user.id,
            goedgekeurd_op=datetime.now(timezone.utc),
            data={
                "restaurant_type": ["hotel restaurant", "casual dining"],
                "culinaire_stijl": ["Internationaal", "Aziatische fusion", "Mediterraan", "Nederlands"],
                "prijssegment": "middensegment",
                "doelgroep": ["hotelgasten", "zakenreizigers", "gezinnen", "lokale bewoners", "koppels"],
                "waardepropositie": "Breed en toegankelijk menu dat klassieke Van der Valk-gerechten combineert met moderne invloeden zoals pok\u00e9 bowls, pad thai en plantaardige opties. Gelegen nabij Rotterdam, trekt zowel hotelgasten als lokale bezoekers. Focus op herkenbare kwaliteit met verrassende specials.",
                "sterke_punten": [
                    "Zeer breed aanbod (15+ voorgerechten, ruime vis- en vleessectie)",
                    "Sterke vegan/vegetarische sectie met eigen categorie",
                    "Aziatische fusion-elementen (pok\u00e9 bowl, pad thai, sasat\u00e9)",
                    "Premium vlees (Iberico, Angus Shortrib, Ribeye 350g)",
                    "Trendy nagerechten (Dubai Chocolade, Proeverij Sue Rotterdam)"
                ],
                "verbeterpunten": [
                    "Sommige klassiekers kunnen gemoderniseerd (garnituren)",
                    "Seizoensgebondenheid kan sterker benadrukt",
                    "Storytelling over herkomst ingredi\u00ebnten ontbreekt"
                ],
                "concurrentiepositie": "Onderscheidt zich van andere Van der Valk-vestigingen door sterke Aziatische fusion-invloeden en een modern dessertaanbod. Concurreert in de regio Rotterdam met standalone restaurants op innovatie, maar wint op breedte en prijs-kwaliteit."
            }
        )
        db.session.add(segment)

        # ── 4. Menu (exact van PDF: 2025-diner-okt-nl.pdf) ──
        menu_data = {
            "categorie\u00ebn": [
                {
                    "naam": "Voorgerechten",
                    "gerechten": [
                        {"naam": "Pok\u00e9 Bowl", "beschrijving": "Sushirijst, mango, wakame, sojabonen, avocado, wortel, zeewierchips, sesam-sojadressing", "prijs": 12.50, "tags": ["Aziatisch", "fusion"], "dieet": ["vegetarisch"]},
                        {"naam": "Seizoenssalade", "beschrijving": "Pompoen, gele winterpeen, gele rozijnen, bonen, bladpeterselie, kruidendressing", "prijs": 12.50, "tags": ["seizoen", "salade"], "dieet": ["vegan"]},
                        {"naam": "Burrata", "beschrijving": "Burrata, perzik, Serranoham, rucola, tomaat, basilicum, aceto-stroop", "prijs": 14.50, "tags": ["Italiaans", "premium"], "dieet": []},
                        {"naam": "Gerookte Zalm", "beschrijving": "Bosui, rettich, sesam-sojadressing, Japanse mayonaise", "prijs": 15.50, "tags": ["vis", "Aziatisch"], "dieet": []},
                        {"naam": "Carpaccio", "beschrijving": "Parmezaanse kaas, bieslook, gebakken spekjes, pijnboompitten, truffelmayonaise", "prijs": 14.50, "tags": ["klassiek"], "dieet": []},
                        {"naam": "Vitello Tonnato", "beschrijving": "Gebraden kalfsmuis, tonijnmayonaise, kapperappels, rucola", "prijs": 15.50, "tags": ["Italiaans", "klassiek"], "dieet": []},
                        {"naam": "Caesarsalade", "beschrijving": "Romeinse sla, Caesardressing, Parmezaanse kaas, cherrytomaat, rode ui, croutons, ei", "prijs": 12.50, "tags": ["klassiek", "salade"], "dieet": ["vegetarisch"]},
                        {"naam": "Salade Geitenkaas", "beschrijving": "Babyleaf, zoetzure komkommer, cherrytomaten, bosbessen, peer, gesuikerde walnoten, honingkruidendressing", "prijs": 14.50, "tags": ["salade"], "dieet": ["vegetarisch"]},
                        {"naam": "Ham & Meloen", "beschrijving": "Serranoham, meloen, granaatappel, pijnboompitten", "prijs": 14.50, "tags": ["klassiek"], "dieet": []},
                        {"naam": "Iberico", "beschrijving": "Iberico, gamba, aioli, antiboise, Parmezaan", "prijs": 19.50, "tags": ["premium", "Spaans"], "dieet": []},
                        {"naam": "Vispalet", "beschrijving": "Zalm, krab, gamba, aardappel, bieslook, kerriedressing", "prijs": 19.50, "tags": ["vis", "premium"], "dieet": []},
                        {"naam": "Cobb Salade", "beschrijving": "Little gem, tomaat, avocado, rode ui, ei, spek, ranchdressing", "prijs": 14.50, "tags": ["Amerikaans", "salade"], "dieet": []},
                        {"naam": "Tonijn", "beschrijving": "Gebrande tonijn, citrusmayonaise, zeewierchips, sesamzaad, wasabikruim", "prijs": 17.50, "tags": ["vis", "Aziatisch", "premium"], "dieet": []},
                        {"naam": "Tomatensoep", "beschrijving": "Volgens ons vertrouwde recept", "prijs": 6.50, "tags": ["soep", "klassiek"], "dieet": ["vegetarisch"]},
                        {"naam": "Bisque", "beschrijving": "Verse kreeftenbisque", "prijs": 8.50, "tags": ["soep", "premium", "vis"], "dieet": []}
                    ]
                },
                {
                    "naam": "Vis",
                    "gerechten": [
                        {"naam": "Zalm", "beschrijving": "Zalm, groenten, aardappelgarnituur, Hollandaisesaus", "prijs": 26.50, "tags": ["vis", "klassiek"], "dieet": []},
                        {"naam": "Pad Thai met Gamba", "beschrijving": "Noedels, gamba, knoflook, bosui, cashewnoten, taug\u00e9, rode peper, limoen", "prijs": 24.50, "tags": ["Aziatisch", "fusion"], "dieet": []},
                        {"naam": "Tongschar", "beschrijving": "Tongschar, rivierkreeftenstaartjes, gesmoorde prei, groentechips, aardappelpuree, beurre blanc, zalmkuit", "prijs": 27.50, "tags": ["vis", "premium", "Frans"], "dieet": []},
                        {"naam": "Heilbot", "beschrijving": "Heilbot, polenta, traybake, paddenstoelen, rodewijnjus", "prijs": 28.50, "tags": ["vis", "premium"], "dieet": []},
                        {"naam": "Schelvis", "beschrijving": "Schelvis, ratatouille, tomatentapenade, Roseval-aardappeltjes", "prijs": 24.50, "tags": ["vis", "Mediterraan"], "dieet": []},
                        {"naam": "Sliptongen", "beschrijving": "2 stuks sliptong, wortel, aardappelgarnituur, peterselie, roomboter, citroen", "prijs": 26.50, "tags": ["vis", "klassiek"], "dieet": []}
                    ]
                },
                {
                    "naam": "Vegan / Vegetarisch",
                    "gerechten": [
                        {"naam": "Spaghetti Bolognese", "beschrijving": "Spaghetti, vegan gehakt, tomatensaus, verse groenten", "prijs": 18.50, "tags": ["Italiaans", "pasta"], "dieet": ["vegan"]},
                        {"naam": "Rigatoni Cacio e Pepe", "beschrijving": "Rigatoni, romige kaassaus, Parmezaanse kaas, peterselie", "prijs": 18.50, "tags": ["Italiaans", "pasta"], "dieet": ["vegetarisch"]},
                        {"naam": "Groente Tajine", "beschrijving": "Couscous, zoete aardappel, traybake, kikkererwten, rozijnen, koriander, olijven", "prijs": 19.50, "tags": ["Marokkaans", "wereldkeuken"], "dieet": ["vegan"]},
                        {"naam": "Risotto", "beschrijving": "Risotto, peer, gorgonzola, walnoot", "prijs": 18.50, "tags": ["Italiaans"], "dieet": ["vegetarisch"]},
                        {"naam": "'Geen Kip' Sat\u00e9", "beschrijving": "Plantaardige kip, sat\u00e9saus, nasi, zoetzure komkommer, cassavekroepoek, krokante uitjes", "prijs": 21.50, "tags": ["plantaardig", "Aziatisch"], "dieet": ["vegan"]}
                    ]
                },
                {
                    "naam": "Vlees",
                    "gerechten": [
                        {"naam": "Tournedos", "beschrijving": "Groenten, aardappelgarnituur", "prijs": 31.50, "tags": ["vlees", "premium"], "dieet": []},
                        {"naam": "Tournedos Speciaal", "beschrijving": "Ui, spek, champignon", "prijs": 34.50, "tags": ["vlees", "premium"], "dieet": []},
                        {"naam": "Oosterse Kipsat\u00e9", "beschrijving": "Sat\u00e9saus, nasi, zoetzure komkommer, kroepoek, krokante uitjes", "prijs": 22.50, "tags": ["Aziatisch", "klassiek"], "dieet": []},
                        {"naam": "Varkenshaas", "beschrijving": "Groenten, aardappelgarnituur", "prijs": 23.50, "tags": ["vlees"], "dieet": []},
                        {"naam": "Varkenshaas Speciaal", "beschrijving": "Ui, spek, champignon", "prijs": 26.50, "tags": ["vlees"], "dieet": []},
                        {"naam": "Cordon Bleu van Kipfilet", "beschrijving": "Groenten, aardappelgarnituur", "prijs": 23.50, "tags": ["vlees", "klassiek"], "dieet": []},
                        {"naam": "Varkensschnitzel", "beschrijving": "Groenten, aardappelgarnituur", "prijs": 22.50, "tags": ["vlees", "klassiek"], "dieet": []},
                        {"naam": "Varkensschnitzel Speciaal", "beschrijving": "Ui, spek, champignon", "prijs": 25.50, "tags": ["vlees"], "dieet": []},
                        {"naam": "Runder Ribeye 350 gram", "beschrijving": "Runder ribeye, geroosterde bloemkool, gefrituurde ui, verse kriel, cowboy butter", "prijs": 34.50, "tags": ["vlees", "premium"], "dieet": []},
                        {"naam": "Pluma Iberico", "beschrijving": "Ibericoschouder, Roseval-aardappeltjes, groene asperge, mango-habanero salsa", "prijs": 24.50, "tags": ["vlees", "premium", "Spaans"], "dieet": []},
                        {"naam": "Angus Shortrib", "beschrijving": "Rundershortrib, aardappelpuree, paddenstoelen, rodewijnjus", "prijs": 32.50, "tags": ["vlees", "premium"], "dieet": []}
                    ]
                },
                {
                    "naam": "Nagerechten",
                    "gerechten": [
                        {"naam": "Heisse Liebe", "beschrijving": "Vanille-ijs, frambozensaus, slagroom", "prijs": 8.50, "tags": ["dessert", "klassiek"], "dieet": ["vegetarisch"]},
                        {"naam": "Dame Blanche", "beschrijving": "Vanille-ijs, witte chocolade, chocoladesaus, crumble, slagroom", "prijs": 8.50, "tags": ["dessert", "klassiek"], "dieet": ["vegetarisch"]},
                        {"naam": "Bananensplit", "beschrijving": "Karamelijs, bananenijs, banaan, karamel, karamelsaus, slagroom", "prijs": 8.50, "tags": ["dessert", "klassiek"], "dieet": ["vegetarisch"]},
                        {"naam": "Fudge Brownie", "beschrijving": "Chocolade brownie, notenspread, karamel-zeezoutsaus, Oreo", "prijs": 9.50, "tags": ["dessert", "Amerikaans"], "dieet": ["vegetarisch"]},
                        {"naam": "Stoofpeer Sorbet", "beschrijving": "Stoofpeer, kaneelijs, stoofpeerijs, slagroom", "prijs": 8.50, "tags": ["dessert", "seizoen", "Nederlands"], "dieet": ["vegetarisch"]},
                        {"naam": "Proeverij van Sue Rotterdam", "beschrijving": "Choco-pistache, stroopwafel, lavendel lemon, flower bite", "prijs": 11.50, "tags": ["dessert", "premium", "lokaal"], "dieet": ["vegetarisch"]},
                        {"naam": "Klassieke Tiramisu", "beschrijving": "Lange vingers, espresso, cacao, mascarpone, Kahl\u00faa", "prijs": 9.50, "tags": ["dessert", "Italiaans"], "dieet": ["vegetarisch"]},
                        {"naam": "Kaasplateau", "beschrijving": "Compote van appel en peer, kletzenbrood, druiven", "prijs": 11.50, "tags": ["kaas", "premium"], "dieet": ["vegetarisch"]},
                        {"naam": "Dubai Chocolade Dessert", "beschrijving": "Chocolade, pistache, kataifi, witte-chocoladeganache, chocolade-ijs", "prijs": 8.50, "tags": ["dessert", "trendy", "viral"], "dieet": ["vegetarisch"]},
                        {"naam": "Cr\u00e8me Br\u00fbl\u00e9e", "beschrijving": "Klassieke cr\u00e8me br\u00fbl\u00e9e", "prijs": 6.00, "tags": ["dessert", "Frans", "klassiek"], "dieet": ["vegetarisch"]}
                    ]
                }
            ]
        }

        menu = Menu(
            organisatie_id=org.id,
            naam="Dinerkaart Oktober 2025",
            bron_type="pdf",
            bron_bestand="2025-diner-okt-nl.pdf",
            data=menu_data,
            actief=True,
            geupload_door=user.id
        )
        db.session.add(menu)
        db.session.flush()

        for cat in menu_data["categorie\u00ebn"]:
            for g in cat["gerechten"]:
                # Ingredi\u00ebnten ophalen en converteren van tuples naar dicts
                raw = INGREDIENTEN.get(g["naam"], [])
                ing_data = [{"naam": n, "categorie": c, "hoeveelheid": h, "eenheid": e} for n, c, h, e in raw]
                gerecht = Gerecht(
                    menu_id=menu.id,
                    organisatie_id=org.id,
                    categorie=cat["naam"],
                    naam=g["naam"],
                    prijs=g.get("prijs"),
                    beschrijving=g.get("beschrijving", ""),
                    tags=g.get("tags", []),
                    dieet=g.get("dieet", []),
                    ingredienten=ing_data
                )
                db.session.add(gerecht)
        db.session.flush()

        # ── 5. TrendGeheugen ──
        geheugen = TrendGeheugen(
            organisatie_id=org.id,
            versie=2,
            data={
                "trends": [
                    {
                        "naam": "Aziatische fusion in de mainstream",
                        "beschrijving": "Pok\u00e9 bowls, pad thai, yuzu, wasabi, sesam-sojadressings en Japanse mayo verspreiden zich van streetfood naar hotelrestaurants. Niet meer niche, maar verwacht door gasten.",
                        "categorie": "voorgerechten",
                        "basis_score": 8.5, "effectieve_score": 9.2, "bevestigingen": 3,
                        "eerste_gezien": "2025-08-15T10:00:00Z", "laatst_bevestigd": "2025-10-01T14:30:00Z",
                        "tags": ["Aziatisch", "fusion", "pok\u00e9", "umami"], "bronnen": ["Culy.nl", "Thuisbezorgd Trends 2025"], "status": "actief"
                    },
                    {
                        "naam": "Plant-forward & vegan als volwaardige categorie",
                        "beschrijving": "Restaurants met een aparte vegan/vegetarische sectie op de kaart presteren beter. 'Geen Kip' sat\u00e9, groente tajine en vegan bolognese zijn geen concessie meer maar eigen gerechten.",
                        "categorie": "vegan_veg",
                        "basis_score": 8.2, "effectieve_score": 8.9, "bevestigingen": 3,
                        "eerste_gezien": "2025-08-15T10:00:00Z", "laatst_bevestigd": "2025-10-01T14:30:00Z",
                        "tags": ["plantaardig", "vegan", "duurzaam"], "bronnen": ["Food Inspiration", "Misset Horeca"], "status": "actief"
                    },
                    {
                        "naam": "Virale desserts & social media impact",
                        "beschrijving": "Dubai chocolade, creatieve brownie-variaties en instagrammable desserts trekken jonge doelgroepen. Samenwerking met lokale patissiers (bijv. Sue Rotterdam) versterkt het verhaal.",
                        "categorie": "nagerechten",
                        "basis_score": 7.8, "effectieve_score": 8.4, "bevestigingen": 2,
                        "eerste_gezien": "2025-09-01T09:00:00Z", "laatst_bevestigd": "2025-10-01T14:30:00Z",
                        "tags": ["viral", "social media", "dessert", "Dubai chocolade"], "bronnen": ["Instagram trends", "RTL Nieuws"], "status": "actief"
                    },
                    {
                        "naam": "Premium vlees met herkomstverhaal",
                        "beschrijving": "Gasten betalen meer voor Iberico, Angus en dry-aged vlees als de herkomst duidelijk is. Cowboy butter, mango-habanero salsa en andere creatieve sauzen verhogen de beleving.",
                        "categorie": "vlees",
                        "basis_score": 7.5, "effectieve_score": 8.1, "bevestigingen": 2,
                        "eerste_gezien": "2025-09-01T09:00:00Z", "laatst_bevestigd": "2025-10-01T14:30:00Z",
                        "tags": ["premium", "Iberico", "Angus", "herkomst"], "bronnen": ["Hospitality NL", "De Volkskrant"], "status": "actief"
                    },
                    {
                        "naam": "Seizoensgebonden wisselkaart",
                        "beschrijving": "Pompoen in de herfst, asperges in het voorjaar. Gasten verwachten een menukaart die meebeweegt met de seizoenen. Seizoenssalades en stoofpeer-desserts scoren goed.",
                        "categorie": "voorgerechten",
                        "basis_score": 7.5, "effectieve_score": 7.5, "bevestigingen": 1,
                        "eerste_gezien": "2025-10-01T14:30:00Z", "laatst_bevestigd": "2025-10-01T14:30:00Z",
                        "tags": ["seizoen", "lokaal", "vers", "pompoen"], "bronnen": ["Thuisbezorgd Trends 2025"], "status": "actief"
                    },
                    {
                        "naam": "Comfort classics met een twist",
                        "beschrijving": "Schnitzel, sat\u00e9 en dame blanche blijven populair maar krijgen een upgrade: speciaal-varianten, betere garnituren, ambachtelijke sauzen.",
                        "categorie": "vlees",
                        "basis_score": 7.2, "effectieve_score": 7.2, "bevestigingen": 1,
                        "eerste_gezien": "2025-10-01T14:30:00Z", "laatst_bevestigd": "2025-10-01T14:30:00Z",
                        "tags": ["comfort", "nostalgie", "upgrade"], "bronnen": ["Misset Horeca"], "status": "actief"
                    },
                    {
                        "naam": "Wereldkeuken in hotelrestaurants",
                        "beschrijving": "Tajine, ceviche, pad thai en risotto naast schnitzel en tournedos. Hotelgasten verwachten een internationale kaart. Authenticiteit in bereidingswijze maakt het verschil.",
                        "categorie": "voorgerechten",
                        "basis_score": 7.0, "effectieve_score": 7.0, "bevestigingen": 1,
                        "eerste_gezien": "2025-10-01T14:30:00Z", "laatst_bevestigd": "2025-10-01T14:30:00Z",
                        "tags": ["wereldkeuken", "internationaal", "diversiteit"], "bronnen": ["Food Inspiration"], "status": "actief"
                    },
                    {
                        "naam": "Lokale samenwerkingen & storytelling",
                        "beschrijving": "Samenwerking met lokale producenten en patissiers (Sue Rotterdam, lokale brouwerijen) versterkt het merkverhaal en creëert unieke verkoopargumenten.",
                        "categorie": "nagerechten",
                        "basis_score": 6.8, "effectieve_score": 6.8, "bevestigingen": 1,
                        "eerste_gezien": "2025-10-01T14:30:00Z", "laatst_bevestigd": "2025-10-01T14:30:00Z",
                        "tags": ["lokaal", "storytelling", "samenwerking"], "bronnen": ["Hospitality NL"], "status": "actief"
                    }
                ],
                "statistieken": {"totaal_actief": 8, "nieuw_deze_run": 4, "bevestigd_deze_run": 4, "verouderd": 0, "verlopen_verwijderd": 0}
            }
        )
        db.session.add(geheugen)

        # ── 6. TrendAnalyse ──
        analyse = TrendAnalyse(
            organisatie_id=org.id,
            gegenereerd_door=user.id,
            versie=2,
            data={
                "trends": [
                    {"naam": "Aziatische fusion in de mainstream", "beschrijving": "Pok\u00e9, pad thai, sesam-soja en wasabi zijn standaard geworden in hotelrestaurants.", "categorie": "voorgerechten", "relevantie_score": 8.5, "tags": ["Aziatisch", "fusion"]},
                    {"naam": "Plant-forward & vegan als volwaardige categorie", "beschrijving": "Aparte vegan sectie op de kaart is de norm.", "categorie": "vegan_veg", "relevantie_score": 8.2, "tags": ["plantaardig", "vegan"]},
                    {"naam": "Virale desserts & social media impact", "beschrijving": "Dubai chocolade en samenwerkingen met lokale patissiers.", "categorie": "nagerechten", "relevantie_score": 7.8, "tags": ["viral", "dessert"]},
                    {"naam": "Premium vlees met herkomstverhaal", "beschrijving": "Iberico, Angus en creatieve sauzen.", "categorie": "vlees", "relevantie_score": 7.5, "tags": ["premium", "herkomst"]},
                    {"naam": "Seizoensgebonden wisselkaart", "beschrijving": "Menu dat meebeweegt met de seizoenen.", "categorie": "voorgerechten", "relevantie_score": 7.5, "tags": ["seizoen", "lokaal"]},
                    {"naam": "Comfort classics met een twist", "beschrijving": "Klassiekers met upgrade.", "categorie": "vlees", "relevantie_score": 7.2, "tags": ["comfort", "upgrade"]}
                ],
                "samenvatting": "Van der Valk Ridderkerk loopt voorop met Aziatische fusion (pok\u00e9, pad thai, wasabi-elementen) en een sterke vegan/vegetarische sectie. De Dubai Chocolade en Proeverij van Sue Rotterdam tonen oog voor virale trends en lokale samenwerkingen. Verbeterkansen liggen in het verder moderniseren van klassieke garnituren en het toevoegen van seizoensinformatie en herkomstverhalen op de kaart."
            }
        )
        db.session.add(analyse)
        db.session.flush()

        # ── 7. TrendConfig ──
        trend_config = TrendConfig(
            organisatie_id=org.id,
            data={
                "categorieen": {
                    "voorgerechten": True,
                    "soepen": True,
                    "vis": True,
                    "vegan_veg": True,
                    "vlees": True,
                    "nagerechten": True,
                    "dranken": False
                },
                "inspiratiebronnen": ["michelin", "asian_fusion", "tiktok", "horeca_nl", "culy"],
                "focusthemas": ["plantaardig", "seizoen", "fusion", "social_media", "premium"],
                "custom_prompt": "",
                "suggesties": [
                    {
                        "type": "voeg_focus_toe",
                        "key": "nostalgie",
                        "label": "Nostalgie / comfort food",
                        "reden": "Komt 4x voor in actieve trends"
                    },
                    {
                        "type": "voeg_focus_toe",
                        "key": "lokaal",
                        "label": "Lokaal & ambachtelijk",
                        "reden": "Komt 2x voor in actieve trends"
                    }
                ]
            }
        )
        db.session.add(trend_config)

        # ── 8. MenuAnnotaties ──
        gerechten = Gerecht.query.filter_by(menu_id=menu.id).all()
        annotatie_map = {
            # --- VOORGERECHTEN ---
            "Pok\u00e9 Bowl": {"status": "HOUDEN", "score": 9.0, "opmerkingen": "Uitstekend trendy gerecht dat perfect aansluit bij de Aziatische fusion-trend. Zeewierchips en sesam-sojadressing zijn on point.", "suggesties": [], "relevante_trends": ["Aziatische fusion in de mainstream"], "positief": ["Zeer trending", "Goede base + toppings opzet"]},
            "Seizoenssalade": {"status": "HOUDEN", "score": 8.5, "opmerkingen": "Sterk seizoensgerecht met vegan-status. Pompoen en winterpeen passen perfect bij het herfstmenu.", "suggesties": [], "relevante_trends": ["Seizoensgebonden wisselkaart", "Plant-forward"], "positief": ["Seizoensgebonden", "Vegan"]},
            "Burrata": {"status": "HOUDEN", "score": 8.0, "opmerkingen": "Populair en premium voorgerecht. Combinatie met perzik en aceto-stroop is eigentijds.", "suggesties": [], "relevante_trends": ["Premium vlees met herkomstverhaal"], "positief": ["Premium ingredi\u00ebnt", "Instagrammable"]},
            "Gerookte Zalm": {"status": "HOUDEN", "score": 8.5, "opmerkingen": "Uitstekende fusion: Nederlandse gerookte zalm met Japanse accenten (rettich, sesam-soja, Japanse mayo).", "suggesties": [], "relevante_trends": ["Aziatische fusion in de mainstream"], "positief": ["Creatieve fusion", "Unieke combinatie"]},
            "Carpaccio": {"status": "AANPASSEN", "score": 6.0, "opmerkingen": "Klassieke Van der Valk-standaard maar de meest voorspelbare kaart. Spekjes en truffelmayo voelen gedateerd.", "suggesties": ["Vervang spekjes door krokante kappertjes of sesamkruim", "Overweeg een seizoensvariant (biet, tonijn)", "Voeg ponzu of yuzu toe als dressing-alternatief"], "relevante_trends": ["Aziatische fusion in de mainstream", "Seizoensgebonden wisselkaart"], "positief": ["Herkenbaar voor gasten"]},
            "Vitello Tonnato": {"status": "HOUDEN", "score": 7.5, "opmerkingen": "Italiaanse klassieker die goed past bij het premium segment. Tijdloos gerecht.", "suggesties": [], "relevante_trends": ["Comfort classics met een twist"], "positief": ["Premium uitstraling", "Authentiek Italiaans"]},
            "Caesarsalade": {"status": "AANPASSEN", "score": 6.5, "opmerkingen": "Solide maar zeer standaard. Kan moderner met creatievere toppings.", "suggesties": ["Voeg gegrilde avocado of kimchi toe", "Overweeg een kale caesar als variant"], "relevante_trends": ["Aziatische fusion in de mainstream", "Plant-forward"], "positief": ["Breed gewaardeerd"]},
            "Salade Geitenkaas": {"status": "HOUDEN", "score": 7.5, "opmerkingen": "Goed vegetarisch voorgerecht met mooie smaakcombinaties (bosbessen, peer, walnoten).", "suggesties": [], "relevante_trends": ["Plant-forward"], "positief": ["Vegetarisch", "Seizoenspotentieel"]},
            "Ham & Meloen": {"status": "VERVANGEN", "score": 4.5, "opmerkingen": "Meest gedateerde gerecht op de kaart. Past niet bij de verder moderne richting van het menu.", "suggesties": ["Vervang door burrata met seizoensfruit", "Of: crudo van vis met meloen en yuzu", "Of: upgrade naar Iberico-plank met gegrild fruit"], "relevante_trends": ["Seizoensgebonden wisselkaart", "Premium vlees met herkomstverhaal"], "positief": ["Herkenbaar concept"]},
            "Iberico": {"status": "HOUDEN", "score": 8.0, "opmerkingen": "Premium sharing-gerecht dat past bij de trend van kwaliteitsvlees. Antiboise en gamba geven het een mediterraans karakter.", "suggesties": [], "relevante_trends": ["Premium vlees met herkomstverhaal"], "positief": ["Premium", "Goed als sharing"]},
            "Vispalet": {"status": "HOUDEN", "score": 7.5, "opmerkingen": "Breed visvoorgerecht met goede variatie. Kerriedressing is een leuke twist.", "suggesties": [], "relevante_trends": ["Wereldkeuken in hotelrestaurants"], "positief": ["Variatie in vis", "Creatieve dressing"]},
            "Cobb Salade": {"status": "AANPASSEN", "score": 6.0, "opmerkingen": "Amerikaans concept dat wat gedateerd aanvoelt. Ranchdressing is niet meer van deze tijd.", "suggesties": ["Moderniseer de dressing (yuzu-ranch, miso-dressing)", "Voeg avocado-cr\u00e8me toe als basis"], "relevante_trends": ["Aziatische fusion in de mainstream"], "positief": ["Stevige maaltijdsalade"]},
            "Tonijn": {"status": "HOUDEN", "score": 9.0, "opmerkingen": "Topgerecht: gebrande tonijn met wasabikruim en zeewierchips is precies waar de markt naartoe beweegt.", "suggesties": [], "relevante_trends": ["Aziatische fusion in de mainstream"], "positief": ["Zeer trendy", "Premium ingredi\u00ebnt", "Perfecte fusion"]},
            "Tomatensoep": {"status": "HOUDEN", "score": 7.0, "opmerkingen": "Vertrouwd recept dat hoort bij Van der Valk. Scherpe prijs, altijd populair.", "suggesties": [], "relevante_trends": ["Comfort classics met een twist"], "positief": ["Scherpe prijs", "Huisgemaakt karakter"]},
            "Bisque": {"status": "HOUDEN", "score": 7.5, "opmerkingen": "Premium soep-optie die het menu verrijkt. Kreeftenbisque is tijdloos.", "suggesties": [], "relevante_trends": ["Premium vlees met herkomstverhaal"], "positief": ["Premium", "Onderscheidend"]},

            # --- VIS ---
            "Zalm": {"status": "AANPASSEN", "score": 6.0, "opmerkingen": "Te standaard: zalm met hollandaisesaus is het meest voorspelbare visgerecht. Vergelijk met de veel creatievere Gerookte Zalm.", "suggesties": ["Vervang Hollandaisesaus door miso-beurre blanc", "Voeg Aziatische garnituur toe (paksoi, sesam)", "Vermeld herkomst (Noors, Schots?)"], "relevante_trends": ["Aziatische fusion in de mainstream", "Lokale samenwerkingen & storytelling"], "positief": ["Populair visgerecht"]},
            "Pad Thai met Gamba": {"status": "HOUDEN", "score": 8.5, "opmerkingen": "Sterke fusion-keuze die perfect past bij de Aziatische trend. Authentieke ingredi\u00ebnten (taug\u00e9, cashew, limoen).", "suggesties": [], "relevante_trends": ["Aziatische fusion in de mainstream", "Wereldkeuken in hotelrestaurants"], "positief": ["Authentiek", "Populair", "Goede prijs"]},
            "Tongschar": {"status": "HOUDEN", "score": 8.5, "opmerkingen": "Premium visgerecht met vakmanschap: rivierkreeftjes, beurre blanc, zalmkuit. Onderscheidend op de kaart.", "suggesties": [], "relevante_trends": ["Premium vlees met herkomstverhaal"], "positief": ["Vakmanschap", "Premium ingredi\u00ebnten"]},
            "Heilbot": {"status": "HOUDEN", "score": 8.0, "opmerkingen": "Creatief en modern: polenta, traybake groenten en rodewijnjus bij vis is een verrassende combinatie.", "suggesties": [], "relevante_trends": ["Seizoensgebonden wisselkaart"], "positief": ["Verrassend", "Premium"]},
            "Schelvis": {"status": "HOUDEN", "score": 7.5, "opmerkingen": "Mediterraans karakter met ratatouille en tomatentapenade. Goede prijs-kwaliteit.", "suggesties": [], "relevante_trends": ["Wereldkeuken in hotelrestaurants"], "positief": ["Mediterraans", "Goede prijs"]},
            "Sliptongen": {"status": "AANPASSEN", "score": 6.5, "opmerkingen": "Klassiek maar conservatief. Roomboter en citroen is erg traditioneel vergeleken met de rest van de viskaart.", "suggesties": ["Voeg een kruidenboter met miso of yuzu toe", "Serveer met seizoensgroenten i.p.v. standaard garnituur"], "relevante_trends": ["Aziatische fusion in de mainstream", "Seizoensgebonden wisselkaart"], "positief": ["Klassieke vissoort", "2 stuks is royaal"]},

            # --- VEGAN / VEGETARISCH ---
            "Spaghetti Bolognese": {"status": "HOUDEN", "score": 7.5, "opmerkingen": "Slimme vegan versie van een klassieker. Herkenbaar voor gasten die plantaardig willen proberen.", "suggesties": [], "relevante_trends": ["Plant-forward & vegan als volwaardige categorie"], "positief": ["Herkenbaar concept", "Vegan"]},
            "Rigatoni Cacio e Pepe": {"status": "HOUDEN", "score": 7.5, "opmerkingen": "Authentiek Italiaans vegetarisch gerecht. Eenvoudig maar effectief.", "suggesties": [], "relevante_trends": ["Plant-forward & vegan als volwaardige categorie", "Wereldkeuken in hotelrestaurants"], "positief": ["Authentiek", "Goed vegetarisch"]},
            "Groente Tajine": {"status": "HOUDEN", "score": 8.5, "opmerkingen": "Uitstekend wereldkeuken-gerecht. Marokkaanse smaken met kikkererwten en couscous. Vegan en vol smaak.", "suggesties": [], "relevante_trends": ["Wereldkeuken in hotelrestaurants", "Plant-forward & vegan als volwaardige categorie"], "positief": ["Vegan", "Vol smaak", "Uniek op de kaart"]},
            "Risotto": {"status": "HOUDEN", "score": 7.0, "opmerkingen": "Goede vegetarische optie. Peer-gorgonzola is een bekende maar smakelijke combinatie.", "suggesties": [], "relevante_trends": ["Plant-forward & vegan als volwaardige categorie"], "positief": ["Seizoenspotentieel", "Smaakvol"]},
            "'Geen Kip' Sat\u00e9": {"status": "HOUDEN", "score": 8.5, "opmerkingen": "Creatief en speels: plantaardig alternatief voor de klassieker. Naam is marketingtechnisch sterk. Inclusief nasi en kroepoek maakt het compleet.", "suggesties": [], "relevante_trends": ["Plant-forward & vegan als volwaardige categorie", "Comfort classics met een twist"], "positief": ["Creatieve naam", "Compleet gerecht", "Vegan"]},

            # --- VLEES ---
            "Tournedos": {"status": "AANPASSEN", "score": 6.5, "opmerkingen": "Premium gerecht maar beschrijving is te minimaal. 'Groenten, aardappelgarnituur' verkoopt niet bij de prijs van \u20ac31,50.", "suggesties": ["Beschrijf de garnituur concreter (welke groenten, welke aardappel)", "Voeg een saus toe aan de beschrijving", "Vermeld vlees-herkomst"], "relevante_trends": ["Premium vlees met herkomstverhaal", "Lokale samenwerkingen & storytelling"], "positief": ["Premium vlees", "Altijd populair"]},
            "Tournedos Speciaal": {"status": "HOUDEN", "score": 7.0, "opmerkingen": "De speciaal-variant met ui, spek en champignon geeft meer beleving. Goede upsell.", "suggesties": [], "relevante_trends": ["Comfort classics met een twist"], "positief": ["Goede upsell", "Meer smaakvol"]},
            "Oosterse Kipsat\u00e9": {"status": "HOUDEN", "score": 7.5, "opmerkingen": "Klassieke Van der Valk-favoriet met Aziatische roots. Compleet gerecht met nasi en kroepoek.", "suggesties": [], "relevante_trends": ["Aziatische fusion in de mainstream", "Comfort classics met een twist"], "positief": ["Populair", "Compleet gerecht"]},
            "Varkenshaas": {"status": "AANPASSEN", "score": 6.0, "opmerkingen": "Te generieke beschrijving. 'Groenten, aardappelgarnituur' mist ieder verkoopargument.", "suggesties": ["Beschrijf de garnituur concreet", "Voeg een kenmerkende saus toe", "Overweeg seizoensgarnituur te benoemen"], "relevante_trends": ["Lokale samenwerkingen & storytelling", "Seizoensgebonden wisselkaart"], "positief": ["Betaalbaar"]},
            "Varkenshaas Speciaal": {"status": "HOUDEN", "score": 6.5, "opmerkingen": "Speciaal-variant geeft meer body, maar beschrijving blijft minimaal.", "suggesties": [], "relevante_trends": ["Comfort classics met een twist"], "positief": ["Goede upsell"]},
            "Cordon Bleu van Kipfilet": {"status": "AANPASSEN", "score": 6.0, "opmerkingen": "Klassiek comfort food maar beschrijving is te kaal. De naam 'van kipfilet' onderscheidt het al van standaard.", "suggesties": ["Beschrijf de vulling (ham, kaas)", "Noem de garnituur concreet"], "relevante_trends": ["Comfort classics met een twist"], "positief": ["Populair comfort food"]},
            "Varkensschnitzel": {"status": "HOUDEN", "score": 7.0, "opmerkingen": "Typisch Van der Valk. Hoort op de kaart, trekt een breed publiek.", "suggesties": [], "relevante_trends": ["Comfort classics met een twist"], "positief": ["Herkenbaar Van der Valk", "Scherpe prijs"]},
            "Varkensschnitzel Speciaal": {"status": "HOUDEN", "score": 7.0, "opmerkingen": "Speciaal-variant biedt goede upsell-mogelijkheid.", "suggesties": [], "relevante_trends": ["Comfort classics met een twist"], "positief": ["Goede upsell"]},
            "Runder Ribeye 350 gram": {"status": "HOUDEN", "score": 9.0, "opmerkingen": "Topgerecht: 350 gram ribeye met geroosterde bloemkool, verse kriel en cowboy butter. Moderne garnituur, premium uitstraling.", "suggesties": [], "relevante_trends": ["Premium vlees met herkomstverhaal"], "positief": ["Premium", "Moderne garnituur", "Cowboy butter is trendy"]},
            "Pluma Iberico": {"status": "HOUDEN", "score": 9.0, "opmerkingen": "Uitstekend: Ibericoschouder met mango-habanero salsa en groene asperge. Precies de combinatie van premium vlees met creatieve saus die gasten zoeken.", "suggesties": [], "relevante_trends": ["Premium vlees met herkomstverhaal", "Wereldkeuken in hotelrestaurants"], "positief": ["Uniek op Van der Valk-kaart", "Creatieve salsa", "Premium"]},
            "Angus Shortrib": {"status": "HOUDEN", "score": 8.5, "opmerkingen": "Low & slow shortrib met rodewijnjus is een sterke keuze. Paddenstoelen en aardappelpuree completeren het.", "suggesties": [], "relevante_trends": ["Premium vlees met herkomstverhaal", "Comfort classics met een twist"], "positief": ["Premium", "Slow-cooked", "Smaakvol"]},

            # --- NAGERECHTEN ---
            "Heisse Liebe": {"status": "HOUDEN", "score": 7.0, "opmerkingen": "Klassiek ijs-dessert dat altijd werkt. Frambozensaus is een lekkere keuze.", "suggesties": [], "relevante_trends": ["Comfort classics met een twist"], "positief": ["Tijdloos", "Scherpe prijs"]},
            "Dame Blanche": {"status": "HOUDEN", "score": 7.0, "opmerkingen": "Van der Valk-klassieker. Witte chocolade en crumble geven een upgrade t.o.v. de standaardversie.", "suggesties": [], "relevante_trends": ["Comfort classics met een twist"], "positief": ["Upgrade op klassieker"]},
            "Bananensplit": {"status": "HOUDEN", "score": 6.5, "opmerkingen": "Nostalgisch dessert dat een bepaald publiek aanspreekt.", "suggesties": [], "relevante_trends": ["Comfort classics met een twist"], "positief": ["Nostalgie"]},
            "Fudge Brownie": {"status": "HOUDEN", "score": 7.5, "opmerkingen": "Moderne twist met notenspread, karamel-zeezout en Oreo. Spreekt jongere doelgroep aan.", "suggesties": [], "relevante_trends": ["Virale desserts & social media impact"], "positief": ["Instagrammable", "Moderne twist"]},
            "Stoofpeer Sorbet": {"status": "HOUDEN", "score": 8.0, "opmerkingen": "Sterk seizoensgebonden dessert. Kaneelijs en stoofpeerijs zijn een creatieve combinatie.", "suggesties": [], "relevante_trends": ["Seizoensgebonden wisselkaart"], "positief": ["Seizoensgebonden", "Creatief"]},
            "Proeverij van Sue Rotterdam": {"status": "HOUDEN", "score": 9.0, "opmerkingen": "Topscorer: lokale samenwerking met Rotterdamse patissier. Vier kleine creaties tonen vakmanschap en verhaal. Perfect als sharing-dessert of bij de koffie.", "suggesties": [], "relevante_trends": ["Lokale samenwerkingen & storytelling", "Virale desserts & social media impact"], "positief": ["Lokale samenwerking", "Uniek", "Premium"]},
            "Klassieke Tiramisu": {"status": "HOUDEN", "score": 7.5, "opmerkingen": "Sterke Italiaanse klassieker met Kahl\u00faa. Altijd een goede keuze.", "suggesties": [], "relevante_trends": ["Comfort classics met een twist"], "positief": ["Authentiek", "Populair"]},
            "Kaasplateau": {"status": "HOUDEN", "score": 7.5, "opmerkingen": "Goed alternatief voor zoete desserts. Compote van appel en peer is een mooie toevoeging.", "suggesties": [], "relevante_trends": ["Seizoensgebonden wisselkaart"], "positief": ["Alternatief voor zoet", "Premium"]},
            "Dubai Chocolade Dessert": {"status": "HOUDEN", "score": 9.0, "opmerkingen": "Viral hit: Dubai chocolade met pistache en kataifi. Perfect ingespeeld op de social media trend. Scherpe prijs voor een trending item.", "suggesties": [], "relevante_trends": ["Virale desserts & social media impact"], "positief": ["Viral trend", "Scherpe prijs", "Instagrammable"]},
            "Cr\u00e8me Br\u00fbl\u00e9e": {"status": "HOUDEN", "score": 7.5, "opmerkingen": "Tijdloze klassieker met een scherpe prijs van \u20ac6. Goede instapper in de kleine nagerechten.", "suggesties": [], "relevante_trends": ["Comfort classics met een twist"], "positief": ["Scherpe prijs", "Tijdloos"]}
        }

        for gerecht in gerechten:
            if gerecht.naam in annotatie_map:
                a = annotatie_map[gerecht.naam]
                annot = MenuAnnotatie(
                    organisatie_id=org.id,
                    menu_id=menu.id,
                    gerecht_id=gerecht.id,
                    trend_geheugen_versie=2,
                    status=a["status"],
                    score=a["score"],
                    data={
                        "opmerkingen": a["opmerkingen"],
                        "suggesties": a["suggesties"],
                        "relevante_trends": a["relevante_trends"],
                        "positief": a["positief"]
                    }
                )
                db.session.add(annot)

        db.session.commit()

        # Statistieken
        total_gerechten = Gerecht.query.filter_by(menu_id=menu.id).count()
        total_annot = MenuAnnotatie.query.filter_by(menu_id=menu.id).count()
        statussen = {}
        for a in MenuAnnotatie.query.filter_by(menu_id=menu.id).all():
            statussen[a.status] = statussen.get(a.status, 0) + 1

        print("\nMock data succesvol aangemaakt!")
        print(f"  Org:         {org.naam}")
        print(f"  Adres:       {org.adres}")
        print(f"  Login:       {user.email} / test0000")
        print(f"  Menu:        {menu.naam} ({total_gerechten} gerechten)")
        print(f"  Trends:      {len(geheugen.data['trends'])} actief (geheugen v{geheugen.versie})")
        print(f"  Annotaties:  {total_annot} van {total_gerechten} gerechten")
        s = ", ".join(f"{k}:{v}" for k, v in statussen.items())
        print(f"  Statussen:   {s}")


if __name__ == "__main__":
    reset_and_seed()
