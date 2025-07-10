import discord
import calendar
from discord.ext import commands
from discord import app_commands
import requests
import os
import random
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
DATABASE_ID = os.getenv("NOTION_DB_ID")

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

    # CODICE DADO VTM:

HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json"
}

CARATTERISTICHE = ["Vigore", "Presenza", "Acume", "Risonanza"]
ABILITA = [
    "Atletica", "Combattimento", "Mira", "Riflessi", "Robustezza",
    "Persuasione", "Intimidazione", "Comando", "Maschera", "Autocontrollo",
    "Osservare", "Analisi", "Tecnica", "Studio", "Cultura",
    "Sintonia", "Conoscenza", "Trasmutazione", "Resilienza", "Salto"
]

MAPPING_CARATTERISTICHE = {
    "Vigore": "VIGORE",
    "Presenza": "PRESENZA",
    "Acume": "ACUME",
    "Risonanza": "RISONANZA"
}
MAPPING_ABILITA = {a: a for a in ABILITA}

class DadoView(discord.ui.View):
    def __init__(self, user_id, personaggi):
        super().__init__(timeout=120)
        self.user_id = user_id
        self.personaggi = {pg["id"]: pg for pg in personaggi}
        self.selected_pg = None

        self.pg_select = discord.ui.Select(
            placeholder="Seleziona il personaggio",
            options=[discord.SelectOption(label=pg["Nome"], value=pg["id"]) for pg in personaggi]
        )
        self.pg_select.callback = self.select_pg
        self.add_item(self.pg_select)

    async def select_pg(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Questo menu non è tuo!", ephemeral=True)
            return

        pg_id = self.pg_select.values[0]
        self.selected_pg = self.personaggi[pg_id]

        abilita_attive = [a for a in ABILITA if (self.selected_pg.get(a) or 0) > 0]

        view = TiroConfigView(self.user_id, self.selected_pg, abilita_attive)
        await interaction.response.edit_message(content=f"Configura il tiro per {self.selected_pg['Nome']}", view=view)

class TiroConfigView(discord.ui.View):
    def __init__(self, user_id, personaggio, abilita_attive):
        super().__init__(timeout=120)
        self.user_id = user_id
        self.personaggio = personaggio

        self.char_select = discord.ui.Select(
            placeholder="Seleziona Caratteristica",
            options=[discord.SelectOption(label=c) for c in CARATTERISTICHE]
        )
        self.char_select.callback = self.select_callback
        self.add_item(self.char_select)

        self.abilita_select = discord.ui.Select(
            placeholder="(Facoltativa) Seleziona Abilità",
            options=[discord.SelectOption(label=a) for a in abilita_attive],
            min_values=0, max_values=1
        )
        self.abilita_select.callback = self.select_callback
        self.add_item(self.abilita_select)

        self.diff_select = discord.ui.Select(
            placeholder="(Facoltativa) Difficoltà (default 7)",
            options=[discord.SelectOption(label=str(i)) for i in range(5, 11)],
            min_values=0, max_values=1
        )
        self.diff_select.callback = self.select_callback
        self.add_item(self.diff_select)

        self.bonus_select = discord.ui.Select(
            placeholder="(Facoltativo) Bonus/Malus d10",
            options=[discord.SelectOption(label=str(i)) for i in range(-5, 6)],
            min_values=0, max_values=1
        )
        self.bonus_select.callback = self.select_callback
        self.add_item(self.bonus_select)

        self.roll_button = discord.ui.Button(label="Tira!", style=discord.ButtonStyle.primary)
        self.roll_button.callback = self.roll_dice
        self.add_item(self.roll_button)

    async def select_callback(self, interaction: discord.Interaction):
        if interaction.user.id == self.user_id:
            await interaction.response.defer(ephemeral=True)

    async def roll_dice(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Questo bottone non è tuo!", ephemeral=True)
            return

        if not self.char_select.values:
            await interaction.response.send_message("❌ Seleziona una Caratteristica!", ephemeral=True)
            return

        caratteristica = self.char_select.values[0]
        abilita = self.abilita_select.values[0] if self.abilita_select.values else None
        difficolta = int(self.diff_select.values[0]) if self.diff_select.values else 7
        bonus = int(self.bonus_select.values[0]) if self.bonus_select.values else 0

        caratteristica_val = self.personaggio.get(caratteristica, 0)
        abilita_val = self.personaggio.get(abilita, 0) if abilita else 0

        dado_totale = caratteristica_val + abilita_val + bonus
        tiri = [random.randint(1, 10) for _ in range(max(dado_totale, 0))]

        successi = 0
        uno = 0
        dettagli = []

        for d in tiri:
            if d >= difficolta:
                successi += 1
                if d == 10:
                    successi += 1
                dettagli.append(f"**__{d}__**")
            elif d == 1:
                uno += 1
                dettagli.append(f"*{d}*")
            else:
                dettagli.append(f"~~{d}~~")

        successi -= uno
        successi = max(0, successi)

        if successi >= 5:
            esito = "🚀 Successo critico!"
        elif successi >= 1:
            esito = "✅ Successo!"
        elif uno > 0:
            esito = "💥 Fallimento critico!"
        else:
            esito = "❌ Fallimento!"

        parola_successo = "Successo" if successi == 1 else "Successi"
        abilita_str = f" + {abilita} {abilita_val}" if abilita else ""

        await interaction.response.defer(ephemeral=True)

        await interaction.channel.send(
            f"🎲 **{self.personaggio['Nome']}** tira {caratteristica} {caratteristica_val}{abilita_str} + {bonus}d10 a Difficoltà {difficolta} = {dado_totale}d10\n"
            f"🎯 Risultati: [{', '.join(dettagli)}], che equivale a **{successi} {parola_successo}**\n"
            f"{esito}"
        )

@tree.command(name="dado", description="Tira un dado per un tuo personaggio")
async def dado(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    discord_id = str(interaction.user.id)
    url = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query"
    payload = {
        "filter": {
            "property": "ID Discord",
            "rich_text": {"equals": discord_id}
        }
    }
    res = requests.post(url, headers=HEADERS, json=payload)
    data = res.json()

    personaggi = []
    for result in data.get("results", []):
        props = result["properties"]
        pg_data = {"id": result["id"], "Nome": props["Nome PG"]["rich_text"][0]["text"]["content"]}

        for stat in CARATTERISTICHE:
            colonna = MAPPING_CARATTERISTICHE.get(stat)
            valore = props.get(colonna, {}).get("number", 0)
            pg_data[stat] = valore if valore is not None else 0

        for stat in ABILITA:
            colonna = MAPPING_ABILITA.get(stat)
            valore = props.get(colonna, {}).get("number", 0)
            pg_data[stat] = valore if valore is not None else 0

        personaggi.append(pg_data)

    if not personaggi:
        await interaction.followup.send("❌ Non ho trovato personaggi legati al tuo ID Discord.", ephemeral=True)
        return

    view = DadoView(interaction.user.id, personaggi)
    await interaction.followup.send("Seleziona il personaggio per il tiro:", view=view, ephemeral=True)


    # CODICE RITIRO STIPENDIO:

CARICA_STIPENDIO = {
    4: 50,
    3: 40,
    2: 25,
    1: 10
}

class StipendioView(discord.ui.View):
    def __init__(self, pg_list, mapping, user_id):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.mapping = mapping
        options = [
            discord.SelectOption(label=pg, description="Ritira stipendio per questo PG")
            for pg in pg_list
        ]
        self.add_item(StipendioSelect(options, mapping, user_id))

class StipendioSelect(discord.ui.Select):
    def __init__(self, options, mapping, user_id):
        super().__init__(placeholder="Scegli il personaggio", min_values=1, max_values=1, options=options)
        self.mapping = mapping
        self.user_id = user_id

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Questo menu non è tuo!", ephemeral=True)
            return

        pg_nome = self.values[0]
        page_id = self.mapping[pg_nome]
        result = paga_personaggio(page_id)
        await interaction.response.edit_message(content=result, view=None)

def paga_personaggio(page_id):
    oggi = datetime.utcnow().date()
    res = requests.get(f"https://api.notion.com/v1/pages/{page_id}", headers=HEADERS)
    data = res.json()["properties"]

    nome_pg = data["Nome PG"]["rich_text"][0]["text"]["content"]
    saldo = data["Croniri"]["number"]
    carica = data["Grado Gilda"]["number"]
    ultimo = data.get("Ultimo Accredito", {}).get("date")
    ultima_data = datetime.strptime(ultimo["start"], "%Y-%m-%d").date() if ultimo else datetime.min.date()

    oggi_mese = oggi.strftime("%Y-%m")
    ultimo_mese = ultima_data.strftime("%Y-%m")

    if ultimo_mese == oggi_mese:
        return f"⏳ **{nome_pg}** ha già ricevuto lo stipendio questo mese."

    giorni_nel_mese = calendar.monthrange(oggi.year, oggi.month)[1]
    stipendio_giornaliero = CARICA_STIPENDIO.get(carica, 0)
    stipendio = stipendio_giornaliero * giorni_nel_mese
    nuovo_saldo = saldo + stipendio

    patch_url = f"https://api.notion.com/v1/pages/{page_id}"
    patch_data = {
        "properties": {
            "Croniri": {"number": nuovo_saldo},
            "Ultimo Accredito": {"date": {"start": oggi.isoformat()}}
        }
    }
    patch_response = requests.patch(patch_url, headers=HEADERS, json=patch_data)

    if patch_response.status_code == 200:
        return (
            f"💰 **{nome_pg}** ha ricevuto Ȼ{stipendio} questo mese ({stipendio_giornaliero} × {giorni_nel_mese} giorni).\n"
            f"💼 Saldo precedente: Ȼ{saldo}\n"
            f"💳 Nuovo saldo: Ȼ{nuovo_saldo}"
        )
    else:
        return f"❌ Errore nel pagare {nome_pg}."

    # CODICE TRASFERIMENTO SOLDI:

@tree.command(name="trasferisci", description="Trasferisci denaro da un tuo PG a un altro PG")
async def trasferisci(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    user_id = str(interaction.user.id)

    url = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query"
    payload = {
        "filter": {
            "property": "ID Discord",
            "rich_text": {"equals": user_id}
        }
    }
    res = requests.post(url, headers=HEADERS, json=payload)
    pg_utente = res.json().get("results", [])

    if len(pg_utente) == 0:
        await interaction.followup.send("❌ Non ho trovato personaggi collegati al tuo ID.", ephemeral=True)
        return

    # Scarica tutti i PG esistenti per selezionare il destinatario
    all_pgs = requests.post(
        f"https://api.notion.com/v1/databases/{DATABASE_ID}/query",
        headers=HEADERS
    ).json().get("results", [])

    destinatari = []
    for pg in all_pgs:
        nome = pg["properties"]["Nome PG"]["rich_text"][0]["text"]["content"]
        pg_id = pg["id"]
        if pg_id not in [p["id"] for p in pg_utente]:
            destinatari.append((nome, pg_id, pg["properties"]["ID Discord"]["rich_text"][0]["text"]["content"]))

    if not destinatari:
        await interaction.followup.send("❌ Nessun destinatario disponibile.", ephemeral=True)
        return

    if len(pg_utente) == 1:
        pg = pg_utente[0]
        mittente_id = pg["id"]
        mittente_nome = pg["properties"]["Nome PG"]["rich_text"][0]["text"]["content"]
        mittente_saldo = pg["properties"]["Croniri"]["number"]

        await interaction.followup.send_modal(TransazioneSelezionaDestinatarioModal(
            mittente_id, mittente_nome, mittente_saldo, destinatari
        ), ephemeral=True)
    else:
        # Scegli PG mittente
        view = discord.ui.View(timeout=60)

        select = discord.ui.Select(
            placeholder="Scegli il tuo PG mittente",
            options=[discord.SelectOption(label=pg["properties"]["Nome PG"]["rich_text"][0]["text"]["content"], value=pg["id"])
                     for pg in pg_utente]
        )

        async def select_callback(inter: discord.Interaction):
            if inter.user.id != interaction.user.id:
                await inter.response.send_message("Non è il tuo menu.", ephemeral=True)
                return

            selected_id = select.values[0]
            selected_pg = next(pg for pg in pg_utente if pg["id"] == selected_id)
            nome = selected_pg["properties"]["Nome PG"]["rich_text"][0]["text"]["content"]
            saldo = selected_pg["properties"]["Croniri"]["number"]

            await inter.response.send_modal(TransazioneSelezionaDestinatarioModal(
                selected_id, nome, saldo, destinatari
            ))

        select.callback = select_callback
        view.add_item(select)
        await interaction.followup.send("Hai più PG. Scegli il mittente:", view=view, ephemeral=True)


class TransazioneSelezionaDestinatarioModal(discord.ui.Modal, title="Trasferimento Croniri"):
    def __init__(self, mittente_id, mittente_nome, mittente_saldo, destinatari):
        super().__init__()
        self.mittente_id = mittente_id
        self.mittente_nome = mittente_nome
        self.mittente_saldo = mittente_saldo
        self.destinatari = destinatari

        self.importo = discord.ui.TextInput(label="Importo da trasferire", required=True, placeholder="Ȼ")
        self.causale = discord.ui.TextInput(label="Causale", required=False, placeholder="Motivo del trasferimento")

        self.add_item(self.importo)
        self.add_item(self.causale)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            importo = int(self.importo.value.strip())
        except ValueError:
            await interaction.response.send_message("❌ L'importo deve essere un numero.", ephemeral=True)
            return

        if importo <= 0:
            await interaction.response.send_message("❌ L'importo deve essere positivo.", ephemeral=True)
            return
        if importo > self.mittente_saldo:
            await interaction.response.send_message("❌ Il tuo personaggio non ha abbastanza Ȼ.", ephemeral=True)
            return

        # Menu a tendina per scegliere il destinatario
        view = discord.ui.View(timeout=60)
        select = discord.ui.Select(
            placeholder="Scegli il PG destinatario",
            options=[discord.SelectOption(label=nome, value=f"{pg_id}|{discord_id}") for nome, pg_id, discord_id in self.destinatari]
        )

        async def destinatario_callback(inter2: discord.Interaction):
            if inter2.user.id != interaction.user.id:
                await inter2.response.send_message("❌ Non sei autorizzato.", ephemeral=True)
                return

            selection = select.values[0]
            destinatario_id, discord_dest_id = selection.split("|")
            destinatario_pg = next(pg for pg in self.destinatari if pg[1] == destinatario_id)
            destinatario_nome = destinatario_pg[0]

            # Prendi saldo attuale destinatario
            res = requests.get(f"https://api.notion.com/v1/pages/{destinatario_id}", headers=HEADERS)
            saldo_dest = res.json()["properties"]["Croniri"]["number"]
            nuovo_mittente = self.mittente_saldo - importo
            nuovo_dest = saldo_dest + importo

            # Aggiorna saldi
            requests.patch(f"https://api.notion.com/v1/pages/{self.mittente_id}",
                           headers=HEADERS,
                           json={"properties": {"Croniri": {"number": nuovo_mittente}}})
            requests.patch(f"https://api.notion.com/v1/pages/{destinatario_id}",
                           headers=HEADERS,
                           json={"properties": {"Croniri": {"number": nuovo_dest}}})

            # Log Notion
            tx_payload = {
                "parent": {"database_id": os.getenv("NOTION_TX_DB_ID")},
                "properties": {
                    "Data": {"date": {"start": datetime.utcnow().isoformat()}},
                    "Importo": {"number": importo},
                    "Mittente": {"relation": [{"id": self.mittente_id}]},
                    "Destinatario": {"relation": [{"id": destinatario_id}]},
                    "Descrizione": {"rich_text": [{"text": {"content": self.causale.value.strip()}}]} if self.causale.value.strip() else {}
                }
            }
            requests.post("https://api.notion.com/v1/pages", headers=HEADERS, json=tx_payload)

            # Notifica mittente
            await inter2.response.send_message(
                f"✅ Hai trasferito Ȼ{importo} a <@{discord_dest_id}> ({destinatario_nome})." +
                (f"\n📄 Causale: {self.causale.value}" if self.causale.value.strip() else ""),
                ephemeral=True
            )

            # Notifica destinatario
            utente_dest = interaction.client.get_user(int(discord_dest_id))
            if utente_dest:
                try:
                    await utente_dest.send(
                        f"📥 Hai ricevuto Ȼ{importo} da <@{interaction.user.id}> ({self.mittente_nome})." +
                        (f"\n📄 Causale: {self.causale.value}" if self.causale.value.strip() else "")
                    )
                except discord.Forbidden:
                    print(f"❌ Impossibile mandare DM a {discord_dest_id}")

        select.callback = destinatario_callback
        view.add_item(select)
        await interaction.followup.send("Scegli il destinatario:", view=view, ephemeral=True)


# CODICI PER DEPLOY:

@bot.event
async def on_ready():
    await tree.sync()
    print(f"✅ Bot online come {bot.user}")

from flask import Flask
from threading import Thread

app = Flask('')

@app.route('/')
def home():
    return "Bot attivo!"

def keep_alive():
    Thread(target=lambda: app.run(host='0.0.0.0', port=8080)).start()
keep_alive()


bot.run(TOKEN)
