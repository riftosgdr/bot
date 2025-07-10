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

@tree.command(name="stipendio", description="Ritira lo stipendio per un tuo personaggio")
async def stipendio(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)

    discord_id = str(interaction.user.id)
    url = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query"
    payload = {
        "filter": {
            "property": "ID Discord",
            "rich_text": {
                "equals": discord_id
            }
        }
    }
    response = requests.post(url, headers=HEADERS, json=payload)
    data = response.json()

    personaggi = data.get("results", [])
    if not personaggi:
        await interaction.followup.send("❌ Non ho trovato personaggi legati al tuo ID Discord.", ephemeral=True)
        return

    if len(personaggi) == 1:
        page_id = personaggi[0]["id"]
        result = paga_personaggio(page_id)
        await interaction.followup.send(result, ephemeral=True)
    else:
        mapping = {}
        pg_list = []
        for pg in personaggi:
            nome_pg = pg["properties"]["Nome PG"]["rich_text"][0]["text"]["content"]
            mapping[nome_pg] = pg["id"]
            pg_list.append(nome_pg)

        view = StipendioView(pg_list, mapping, interaction.user.id)
        await interaction.followup.send("Scegli per quale PG vuoi ritirare lo stipendio:", view=view, ephemeral=True)

@tree.command(name="trasferisci", description="Trasferisci Croniri da un tuo personaggio a un altro")
async def trasferisci(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    
    discord_id = str(interaction.user.id)
    
    # 1. Cerca i personaggi dell'utente (Mittente)
    payload = {
        "filter": {
            "property": "ID Discord",
            "rich_text": {"equals": discord_id}
        }
    }
    res = requests.post(f"https://api.notion.com/v1/databases/{DATABASE_ID}/query", headers=HEADERS, json=payload)
    user_data = res.json()

    personaggi = user_data.get("results", [])
    if not personaggi:
        await interaction.followup.send("❌ Nessun personaggio trovato per il tuo ID.", ephemeral=True)
        return

    # 2. Seleziona PG mittente se l'utente ne ha più di uno
    if len(personaggi) > 1:
        await interaction.followup.send("Hai più di un PG. Questa funzione supporta un solo PG mittente al momento.", ephemeral=True)
        return

    mittente_pg = personaggi[0]
    mittente_id = mittente_pg["id"]
    mittente_props = mittente_pg["properties"]
    nome_mittente = mittente_props["Nome PG"]["rich_text"][0]["text"]["content"]
    saldo_mittente = mittente_props["Croniri"]["number"]

    await interaction.followup.send(f"💼 PG mittente selezionato: **{nome_mittente}** (Saldo: Ȼ{saldo_mittente}). Scrivi ora il **nome esatto** del PG destinatario.", ephemeral=True)

    def check_nome(m):
        return m.author == interaction.user and m.channel == interaction.channel

    try:
        msg_dest = await bot.wait_for('message', timeout=30.0, check=check_nome)
    except:
        await interaction.followup.send("⏰ Tempo scaduto. Riprova il comando.", ephemeral=True)
        return

    nome_dest = msg_dest.content.strip()

    # 3. Cerca destinatario per nome nel database
    payload_dest = {
        "filter": {
            "property": "Nome PG",
            "rich_text": {"equals": nome_dest}
        }
    }
    res_dest = requests.post(f"https://api.notion.com/v1/databases/{DATABASE_ID}/query", headers=HEADERS, json=payload_dest)
    dest_data = res_dest.json().get("results", [])

    if not dest_data:
        await interaction.followup.send("❌ Destinatario non trovato nel database.", ephemeral=True)
        return

    destinatario_pg = dest_data[0]
    destinatario_id = destinatario_pg["id"]
    destinatario_props = destinatario_pg["properties"]
    nome_destinatario = destinatario_props["Nome PG"]["rich_text"][0]["text"]["content"]
    saldo_dest = destinatario_props["Croniri"]["number"]

    await interaction.followup.send(f"📥 Destinatario: **{nome_destinatario}** (Saldo: Ȼ{saldo_dest}). Ora scrivi quanti Croniri vuoi trasferire:", ephemeral=True)

    def check_valore(m):
        return m.author == interaction.user and m.channel == interaction.channel and m.content.isdigit()

    try:
        msg_valore = await bot.wait_for('message', timeout=30.0, check=check_valore)
    except:
        await interaction.followup.send("⏰ Tempo scaduto. Riprova il comando.", ephemeral=True)
        return

    valore = int(msg_valore.content)
    if valore <= 0 or valore > saldo_mittente:
        await interaction.followup.send("❌ Valore non valido. Controlla il saldo.", ephemeral=True)
        return

    nuovo_saldo_mittente = saldo_mittente - valore
    nuovo_saldo_dest = saldo_dest + valore

    # 4. Aggiorna i saldi
    requests.patch(f"https://api.notion.com/v1/pages/{mittente_id}", headers=HEADERS, json={
        "properties": {"Croniri": {"number": nuovo_saldo_mittente}}
    })
    requests.patch(f"https://api.notion.com/v1/pages/{destinatario_id}", headers=HEADERS, json={
        "properties": {"Croniri": {"number": nuovo_saldo_dest}}
    })

    # 5. Registra nel DB transazioni (aggiungi il tuo ID DB transazioni!)
    TRANSAZIONI_DB_ID = os.getenv("NOTION_TX_DB_ID")  # mettilo nel tuo .env

    requests.post("https://api.notion.com/v1/pages", headers=HEADERS, json={
        "parent": {"database_id": TRANSAZIONI_DB_ID},
        "properties": {
            "Mittente": {"relation": [{"id": mittente_id}]},
            "Destinatario": {"relation": [{"id": destinatario_id}]},
            "Importo": {"number": valore},
            "Data": {"date": {"start": datetime.utcnow().isoformat()}}
        }
    })

    await interaction.followup.send(f"✅ Hai trasferito Ȼ{valore} da **{nome_mittente}** a **{nome_destinatario}**.", ephemeral=True)


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
