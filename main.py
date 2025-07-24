import discord
import calendar
from discord.ext import commands
from discord import app_commands
import requests
import os
import random
import unicodedata
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
DATABASE_ID = os.getenv("NOTION_DB_ID")

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json"
}

def normalizza(s):
    s = s.replace("’", "'").strip()
    s = unicodedata.normalize("NFKC", s)
    return s
    
#CODICE DADO
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

SOGLIE = {
    "Bassa": 1,
    "Media": 3,
    "Alta": 5
}

MAPPING_ABILITA = {a: a for a in ABILITA}

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

    try:
        res = requests.post(url, headers=HEADERS, json=payload)
        data = res.json()
    except Exception:
        await interaction.followup.send("❌ Errore nel contattare il database.", ephemeral=True)
        return

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


class DadoView(discord.ui.View):
    def __init__(self, user_id, personaggi):
        super().__init__(timeout=120)
        self.user_id = user_id
        self.personaggi = {pg["id"]: pg for pg in personaggi}
        self.selected_pg = None

        options = [discord.SelectOption(label=pg["Nome"], value=pg["id"]) for pg in personaggi]
        select = discord.ui.Select(placeholder="Seleziona il personaggio", options=options)
        select.callback = self.select_pg
        self.add_item(select)

    async def select_pg(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Questo menu non è tuo!", ephemeral=True)
            return

        self.selected_pg = self.personaggi[interaction.data['values'][0]]
        abilita_attive = [a for a in ABILITA if (self.selected_pg.get(a) or 0) > 0]
        view = PrimaFaseTiroView(self.user_id, self.selected_pg, abilita_attive)
        await interaction.response.edit_message(content=f"Configura il tiro per {self.selected_pg['Nome']}", view=view)

class PrimaFaseTiroView(discord.ui.View):
    def __init__(self, user_id, personaggio, abilita_attive):
        super().__init__(timeout=120)
        self.user_id = user_id
        self.personaggio = personaggio

        self.char_select = discord.ui.Select(
            placeholder="Seleziona Caratteristica",
            options=[discord.SelectOption(label=c) for c in CARATTERISTICHE]
        )
        self.abilita_select = discord.ui.Select(
            placeholder="(Facoltativa) Seleziona Abilità",
            options=[discord.SelectOption(label=a) for a in abilita_attive],
            min_values=0, max_values=1
        )
        self.bonus_select = discord.ui.Select(
            placeholder="(Facoltativo) Bonus/Malus d10",
            options=[discord.SelectOption(label=str(i)) for i in range(-5, 6)],
            min_values=0, max_values=1
        )
        self.continua_button = discord.ui.Button(label="Continua >", style=discord.ButtonStyle.primary)

        self.char_select.callback = self.select_callback
        self.abilita_select.callback = self.select_callback
        self.bonus_select.callback = self.select_callback
        self.continua_button.callback = self.continua

        self.add_item(self.char_select)
        self.add_item(self.abilita_select)
        self.add_item(self.bonus_select)
        self.add_item(self.continua_button)

    async def select_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Non puoi usare questo menu.", ephemeral=True)
            return
        await interaction.response.defer()

    async def continua(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Questo bottone non è tuo!", ephemeral=True)
            return

        caratteristica = self.char_select.values[0]
        abilita = self.abilita_select.values[0] if self.abilita_select.values else None
        bonus = int(self.bonus_select.values[0]) if self.bonus_select.values else 0

        view = SecondaFaseTiroView(self.user_id, self.personaggio, caratteristica, abilita, bonus)
        await interaction.response.edit_message(content="Imposta Difficoltà e Soglia:", view=view)

class SecondaFaseTiroView(discord.ui.View):
    def __init__(self, user_id, personaggio, caratteristica, abilita, bonus):
        super().__init__(timeout=120)
        self.user_id = user_id
        self.personaggio = personaggio
        self.caratteristica = caratteristica
        self.abilita = abilita
        self.bonus = bonus

        self.diff_select = discord.ui.Select(
            placeholder="Difficoltà (Default: 7)",
            options=[discord.SelectOption(label=str(i)) for i in range(5, 11)]
        )
        self.soglia_select = discord.ui.Select(
            placeholder="Soglia di Successo (Default: Bassa)",
            options=[discord.SelectOption(label=nome, value=nome) for nome in SOGLIE.keys()]
        )
        self.roll_button = discord.ui.Button(label="Tira!", style=discord.ButtonStyle.success)

        self.diff_select.callback = self.select_callback
        self.soglia_select.callback = self.select_callback
        self.roll_button.callback = self.roll_dice

        self.add_item(self.diff_select)
        self.add_item(self.soglia_select)
        self.add_item(self.roll_button)

    async def select_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Questo menu non è tuo!", ephemeral=True)
            return
        await interaction.response.defer()

    async def roll_dice(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Questo bottone non è tuo!", ephemeral=True)
            return

        await interaction.response.defer(thinking=True)

        difficolta = int(self.diff_select.values[0]) if self.diff_select.values else 7
        soglia_nome = self.soglia_select.values[0] if self.soglia_select.values else "Bassa"
        soglia = SOGLIE[soglia_nome]

        caratteristica_val = self.personaggio.get(self.caratteristica, 0)
        abilita_val = self.personaggio.get(self.abilita, 0) if self.abilita else 0
        dado_totale = caratteristica_val + abilita_val + self.bonus

        if dado_totale <= 0:
            await interaction.followup.send(
                f"⚠️ {self.personaggio['Nome']} non ha dadi da tirare. Controlla Caratteristica, Abilità e Bonus selezionati.",
                ephemeral=True
            )
            return

        tiri = [random.randint(1, 10) for _ in range(dado_totale)]
        successi = sum(1 for d in tiri if difficolta <= d < 10) + sum(2 for d in tiri if d == 10)
        penalita = sum(1 for d in tiri if d == 1)
        netti = successi - penalita

        dettagli = [f"**{d}**" if d >= difficolta else f"~~{d}~~" for d in tiri]

        if netti <= 0:
            esito = "💥 Fallimento critico!"
        elif netti >= soglia + 3:
            esito = "🚀 Successo critico!"
        elif netti >= soglia:
            esito = "✅ Successo!"
        else:
            esito = "❌ Fallimento."

        await interaction.delete_original_response()
        await interaction.channel.send(
            f"🎲 **{self.personaggio['Nome']}** tira {self.caratteristica} {caratteristica_val}"
            + (f" + {self.abilita} {abilita_val}" if self.abilita else "")
            + f" + {self.bonus} a **Difficoltà {difficolta}** e **Soglia {soglia_nome}** = {dado_totale}d10\n"
            + f"🎯 Risultati: [{', '.join(dettagli)}] → **{max(netti, 0)} Successi**\n"
            + f"{esito}"
        )

    # CODICE RITIRO STIPENDIO:

CARICA_STIPENDIO = {
    0: 0,
    1: 10,
    2: 25,
    3: 40,
    4: 50,
}

@tree.command(name="stipendio", description="Ritira lo stipendio per un tuo personaggio")
async def stipendio(interaction: discord.Interaction):
    discord_id = str(interaction.user.id)
    try:
        await interaction.response.defer(ephemeral=True)
    except discord.NotFound:
        return

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
        await interaction.delete_original_response()
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
        try:
            await interaction.response.defer()
        except discord.NotFound:
            return

        pg_nome = self.values[0]
        page_id = self.mapping[pg_nome]
        result = paga_personaggio(page_id)
        await interaction.delete_original_response()
        await interaction.channel.send(result)


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

@tree.command(name="trasferisci", description="Trasferisci Croniri da un tuo personaggio a un altro")
async def trasferisci(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    try:
        await interaction.response.defer(ephemeral=True)
    except discord.NotFound:
        return

    res = requests.post(f"https://api.notion.com/v1/databases/{DATABASE_ID}/query", headers=HEADERS, json={
        "filter": {"property": "ID Discord", "rich_text": {"equals": user_id}}
    })
    miei_pg = res.json().get("results", [])
    if not miei_pg:
        await interaction.followup.send("❌ Nessun PG trovato legato al tuo account.", ephemeral=True)
        return

    mittente_options = [
        discord.SelectOption(label=pg["properties"]["Nome PG"]["rich_text"][0]["text"]["content"], value=pg["id"])
        for pg in miei_pg
    ]
    mittente_select = discord.ui.Select(placeholder="Scegli il mittente", options=mittente_options)
    mittente_view = discord.ui.View()
    mittente_view.add_item(mittente_select)

    async def mittente_callback(inter):
        if inter.user.id != interaction.user.id:
            await inter.response.send_message("Non puoi usare questo menu.", ephemeral=True)
            return

        try:
            await inter.response.defer()
        except discord.NotFound:
            return

        mittente_id = mittente_select.values[0]
        mittente_pg = next(pg for pg in miei_pg if pg["id"] == mittente_id)
        mittente_nome = mittente_pg["properties"]["Nome PG"]["rich_text"][0]["text"]["content"]
        mittente_saldo = mittente_pg["properties"]["Croniri"]["number"]

        res_all = requests.post(f"https://api.notion.com/v1/databases/{DATABASE_ID}/query", headers=HEADERS)
        tutti_pg = res_all.json().get("results", [])
        pg_dest = [
            pg for pg in tutti_pg
            if pg["id"] != mittente_id and pg["properties"].get("ID Discord", {}).get("rich_text", [{}])[0].get("text", {}).get("content", "") != user_id
        ]

        if not pg_dest:
            await inter.followup.send("❌ Nessun destinatario disponibile.", ephemeral=True)
            return

        options_dest = [
            discord.SelectOption(label=pg["properties"]["Nome PG"]["rich_text"][0]["text"]["content"], value=pg["id"])
            for pg in pg_dest
        ]
        view_dest = discord.ui.View()
        dest_select = discord.ui.Select(placeholder="Scegli il destinatario", options=options_dest)
        view_dest.add_item(dest_select)

        async def dest_callback(dest_inter):
            if dest_inter.user.id != interaction.user.id:
                await dest_inter.response.send_message("Non puoi usare questo menu.", ephemeral=True)
                return

            destinatario_id = dest_select.values[0]
            destinatario_pg = next(pg for pg in pg_dest if pg["id"] == destinatario_id)
            destinatario_nome = destinatario_pg["properties"]["Nome PG"]["rich_text"][0]["text"]["content"]
            destinatario_user_id = destinatario_pg["properties"].get("ID Discord", {}).get("rich_text", [{}])[0].get("text", {}).get("content", "")

            await dest_inter.response.send_modal(
                TransazioneModal(mittente_id, mittente_nome, mittente_saldo, destinatario_id, destinatario_nome, destinatario_user_id)
            )

        dest_select.callback = dest_callback
        await inter.followup.send("Seleziona il destinatario:", view=view_dest, ephemeral=True)

    mittente_select.callback = mittente_callback
    await interaction.followup.send("Hai più di un PG. Scegli il mittente:", view=mittente_view, ephemeral=True)


class TransazioneModal(discord.ui.Modal, title="Trasferimento Croniri"):
    recent_transactions = {}

    def __init__(self, mittente_id, mittente_nome, mittente_saldo, destinatario_id, destinatario_nome, destinatario_user_id):
        super().__init__()
        self.mittente_id = mittente_id
        self.mittente_nome = mittente_nome
        self.mittente_saldo = mittente_saldo
        self.destinatario_id = destinatario_id
        self.destinatario_nome = destinatario_nome
        self.destinatario_user_id = destinatario_user_id

        self.importo = discord.ui.TextInput(label="Importo da trasferire", placeholder="Ȼ", required=True)
        self.causale = discord.ui.TextInput(label="Causale", placeholder="Motivo del trasferimento", required=True)

        self.add_item(self.importo)
        self.add_item(self.causale)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer(thinking=True)
        except discord.NotFound:
            return

        user_key = f"{interaction.user.id}-{self.mittente_id}-{self.destinatario_id}"
        now = datetime.utcnow().timestamp()
        if user_key in self.recent_transactions and now - self.recent_transactions[user_key] < 60:
            await interaction.followup.send("⏳ Aspetta 1 minuto prima di rifare una transazione simile.", ephemeral=True)
            return
        self.recent_transactions[user_key] = now

        try:
            importo = int(self.importo.value.strip())
        except ValueError:
            await interaction.followup.send("❌ L'importo deve essere un numero intero.", ephemeral=True)
            return

        if importo < 1:
            await interaction.followup.send("❌ L'importo minimo trasferibile è 1 Ȼ.", ephemeral=True)
            return
        if importo > self.mittente_saldo:
            await interaction.followup.send("❌ Il tuo personaggio non ha abbastanza Croniri.", ephemeral=True)
            return

        new_mittente = self.mittente_saldo - importo
        requests.patch(
            f"https://api.notion.com/v1/pages/{self.mittente_id}",
            headers=HEADERS,
            json={"properties": {"Croniri": {"number": new_mittente}}}
        )

        res_dest = requests.get(f"https://api.notion.com/v1/pages/{self.destinatario_id}", headers=HEADERS)
        saldo_dest = res_dest.json()["properties"]["Croniri"].get("number", 0)
        new_dest = saldo_dest + importo

        requests.patch(
            f"https://api.notion.com/v1/pages/{self.destinatario_id}",
            headers=HEADERS,
            json={"properties": {"Croniri": {"number": new_dest}}}
        )

        tx_payload = {
            "parent": {"database_id": os.getenv("NOTION_TX_DB_ID")},
            "properties": {
                "Data": {"date": {"start": datetime.utcnow().isoformat()}},
                "Importo": {"number": importo},
                "Causale": {"rich_text": [{"text": {"content": self.causale.value.strip()}}]},
                "Mittente": {"relation": [{"id": self.mittente_id}]},
                "Destinatario": {"relation": [{"id": self.destinatario_id}]}
            }
        }
        requests.post("https://api.notion.com/v1/pages", headers=HEADERS, json=tx_payload)

        messaggio_pubblico = (
            f"💸 **{self.mittente_nome}** ha trasferito Ȼ{importo} a **{self.destinatario_nome}**. "
            f"(<@{interaction.user.id}>, <@{self.destinatario_user_id}>)\n"
            f"📄 Causale: {self.causale.value.strip()}"
        )

        await interaction.delete_original_response()
        await interaction.channel.send(messaggio_pubblico)

############################### GRATTA I SANTI ###############################

@tree.command(name="gratta", description="Tenta la fortuna con Gratta i Santi")
async def gratta(interaction: discord.Interaction):
    discord_id = str(interaction.user.id)
    url = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query"
    payload = {
        "filter": {
            "property": "ID Discord",
            "rich_text": {"equals": discord_id}
        }
    }
    try:
        res = requests.post(url, headers=HEADERS, json=payload)
        data = res.json()
    except Exception:
        await interaction.response.send_message("❌ Errore nel contattare il database.", ephemeral=True)
        return

    personaggi = data.get("results", [])
    if not personaggi:
        await interaction.response.send_message("❌ Nessun PG trovato collegato al tuo ID Discord.", ephemeral=True)
        return

    if len(personaggi) == 1:
        pg = personaggi[0]
        view = GrattaSantiView(pg, interaction.user.id)
        await interaction.response.send_message("🎰 Seleziona la puntata e gratta i santi!", view=view, ephemeral=True)
    else:
        mapping = {}
        options = []
        for pg in personaggi:
            nome = pg["properties"]["Nome PG"]["rich_text"][0]["text"]["content"]
            mapping[nome] = pg
            options.append(discord.SelectOption(label=nome, value=nome))

        class SelezionePG(discord.ui.View):
            def __init__(self, user_id):
                super().__init__(timeout=60)
                self.user_id = user_id
                self.select = discord.ui.Select(placeholder="Scegli il PG", options=options)
                self.select.callback = self.callback
                self.add_item(self.select)

            async def callback(self, i: discord.Interaction):
                if i.user.id != self.user_id:
                    await i.response.send_message("Non puoi usare questo menu.", ephemeral=True)
                    return
                nome = self.select.values[0]
                pg = mapping[nome]
                view = GrattaSantiView(pg, self.user_id)
                await i.response.edit_message(content="🎰 Seleziona la puntata e gratta i santi!", view=view)

        await interaction.response.send_message("Hai più di un PG. Scegli con quale giocare:", view=SelezionePG(interaction.user.id), ephemeral=True)


class GrattaSantiView(discord.ui.View):
    def __init__(self, pg, user_id):
        super().__init__(timeout=60)
        self.pg = pg
        self.user_id = user_id
        self.importo = 10

        self.select = discord.ui.Select(
            placeholder="Scegli quanto vuoi puntare",
            options=[
                discord.SelectOption(label="10 Ȼ", value="10"),
                discord.SelectOption(label="20 Ȼ", value="20"),
                discord.SelectOption(label="50 Ȼ", value="50")
            ]
        )
        self.select.callback = self.select_callback
        self.add_item(self.select)

        self.gratta_button = discord.ui.Button(label="Gratta!", style=discord.ButtonStyle.primary)
        self.gratta_button.callback = self.submit
        self.add_item(self.gratta_button)

    async def select_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Non puoi usare questo menu!", ephemeral=True)
            return
        self.importo = int(self.select.values[0])
        try:
            await interaction.response.defer()
        except discord.NotFound:
            return

   
    async def submit(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Questo bottone non è tuo!", ephemeral=True)
            return

        try:
            await interaction.response.defer(thinking=True)
        except discord.NotFound:
            return

        nome_pg = self.pg["properties"]["Nome PG"]["rich_text"][0]["text"]["content"]
        saldo = self.pg["properties"]["Croniri"].get("number", 0)
        puntata = self.importo

        if saldo < puntata:
            await interaction.followup.send(f"❌ {nome_pg} non ha abbastanza Croniri per questa puntata.", ephemeral=True)
            return

        nuovo_saldo = saldo - puntata
        requests.patch(
            f"https://api.notion.com/v1/pages/{self.pg['id']}",
            headers=HEADERS,
            json={"properties": {"Croniri": {"number": nuovo_saldo}}}
        )

        santi = {
            "San Giorgiorgio": "Nord",
            "Santa Salina": "Est",
            "San Meccano": "Sud",
            "Santa Sciarada": "Ovest",
            "Santa Annina": "Nord-Est",
            "San Iroscio": "Sud-Est",
            "Santa Miralia": "Sud-Ovest",
            "San Abelio": "Nord-Ovest"
        }

        cardinali = {"San Giorgiorgio", "Santa Salina", "San Meccano", "Santa Sciarada"}
        diagonali = {"Santa Annina", "San Iroscio", "Santa Miralia", "San Abelio"}
        estratti = random.sample(list(santi.items()), 4)
        nomi = [nome for nome, _ in estratti]
        direzioni = [direz for _, direz in estratti]

        moltiplicatore = 0
        messaggio = "❌ Ritenta! Sarai più fortunato!"

        if set(nomi) == cardinali:
            moltiplicatore = 5
            messaggio = "🚀 WOW! Hai trovato tutti i Santi Cardinali!"
        elif set(nomi) == diagonali:
            moltiplicatore = 3
            messaggio = "🎉 Ottima vincita! Tutti i Santi Diagonali!"
        else:
            conteggio = {}
            for direz in direzioni:
                for punto in ["Nord", "Sud", "Est", "Ovest"]:
                    if punto in direz:
                        conteggio[punto] = conteggio.get(punto, 0) + 1
            if any(v >= 3 for v in conteggio.values()):
                moltiplicatore = 1.5
                messaggio = "🪙 Vincita minore! 3 Santi allineati per punto cardinale."

        vincita = int(puntata * moltiplicatore)

        if vincita > 0:
            nuovo_saldo += vincita
            requests.patch(
                f"https://api.notion.com/v1/pages/{self.pg['id']}",
                headers=HEADERS,
                json={"properties": {"Croniri": {"number": nuovo_saldo}}}
            )

            tx_payload = {
                "parent": {"database_id": os.getenv("NOTION_TX_DB_ID")},
                "properties": {
                    "Data": {"date": {"start": datetime.utcnow().isoformat()}},
                    "Importo": {"number": vincita - puntata},
                    "Causale": {"rich_text": [{"text": {"content": f"Gratta i Santi: puntata Ȼ{puntata}, vincita Ȼ{vincita}"}}]},
                    "Mittente": {"relation": [{"id": self.pg["id"]}]}
                }
            }
            requests.post("https://api.notion.com/v1/pages", headers=HEADERS, json=tx_payload)

        embed = discord.Embed(title=f"🎛 {nome_pg} ha grattato i Santi!", color=discord.Color.gold())
        embed.add_field(name="🧩 Santi Estratti:", value=" | ".join(nomi), inline=False)
        embed.add_field(name="🎯 Esito:", value=messaggio, inline=False)
        embed.add_field(name="💰 Puntata:", value=f"Ȼ{puntata}", inline=True)
        embed.add_field(name="🏆 Vincita:", value=f"Ȼ{vincita}", inline=True)
        embed.set_image(url="https://i.imgur.com/gxUgDqz.jpeg")

        await interaction.delete_original_response()
        await interaction.channel.send(embed=embed)


# === LIVELLAMENTO PG ===

ABILITA_LIST = [
    "Atletica", "Mira", "Combattimento", "Riflessi", "Robustezza",
    "Analisi", "Osservare", "Studio", "Cultura", "Tecnica",
    "Autocontrollo", "Persuasione", "Comando", "Maschera", "Intimidazione",
    "Sintonia", "Conoscenza", "Trasmutazione", "Resilienza", "Salto"
]

TRATTI_PREGI = ["Intelligente", "Coraggioso", "Empatico"]
TRATTI_DIFETTI = ["Impulsivo", "Distratto", "Testardo"]

INV_LIVELLI = {
    1: "Livello I",
    2: "Livello II",
    3: "Livello III",
    4: "Livello IV",
    5: "Livello V",
    6: "Livello VI"
}

class EndRoleView(discord.ui.View):
    def __init__(self, pg_list, user_id):
        super().__init__(timeout=60)
        self.user_id = user_id
        options = [
            discord.SelectOption(label=pg["properties"]["Nome PG"]["rich_text"][0]["text"]["content"], value=pg["id"])
            for pg in pg_list
        ]
        self.add_item(EndRoleSelect(options, pg_list, user_id))

class EndRoleSelect(discord.ui.Select):
    def __init__(self, options, pg_list, user_id):
        super().__init__(placeholder="Scegli il PG per cui concludi la giocata", min_values=1, max_values=1, options=options)
        self.pg_list = pg_list
        self.user_id = user_id

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Questo menu non è tuo!", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        pg_id = self.values[0]
        pg = next(p for p in self.pg_list if p["id"] == pg_id)
        nome_pg = pg["properties"]["Nome PG"]["rich_text"][0]["text"]["content"]

        now = datetime.utcnow()
        role_count = (pg["properties"].get("Role", {}).get("number") or 0) + 1

        livello = pg["properties"].get("Level", {}).get("number", 1)

        requests.patch(
            f"https://api.notion.com/v1/pages/{pg_id}",
            headers=HEADERS,
            json={
                "properties": {
                    "Ultima Role": {"date": {"start": now.isoformat()}},
                    "Role": {"number": role_count}
                }
            }
        )

        last_level_up = pg["properties"].get("Ultimo Level Up", {}).get("date", {}).get("start")
        last_date = datetime.strptime(last_level_up, "%Y-%m-%d") if last_level_up else now
        giorni_passati = (now - last_date).days

        requisiti = {
            1: (15, 2),
            2: (15, 2),
            3: (30, 3),
            4: (45, 5),
            5: (75, 5),
        }

        if livello < 6 and livello in requisiti:
            giorni, ruolate = requisiti[livello]
            if giorni_passati >= giorni and role_count >= ruolate:
                requests.patch(
                    f"https://api.notion.com/v1/pages/{pg_id}",
                    headers=HEADERS,
                    json={"properties": {"Level Up": {"checkbox": True}}}
                )
                await interaction.followup.send(
                    f"📈 **{nome_pg}** ha raggiunto i requisiti per il {INV_LIVELLI[livello + 1]}!\nUsa il bottone qui sotto per assegnare i punti abilità e scegliere i tratti.",
                    view=LivellaButton(pg), ephemeral=True
                )
                return

        await interaction.followup.send(f"✅ Giocata registrata per {nome_pg}. Totale role: {role_count}.", ephemeral=True)

class LivellaButton(discord.ui.View):
    def __init__(self, pg):
        super().__init__(timeout=60)
        self.pg = pg

    @discord.ui.button(label="Livella PG", style=discord.ButtonStyle.success)
    async def livella_pg(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(LivellaModal(self.pg))

class LivellaModal(discord.ui.Modal, title="Distribuisci i tuoi 5 punti abilità"):
    def __init__(self, pg):
        super().__init__()
        self.pg = pg

        abilita_options = [discord.SelectOption(label=skill, value=skill) for skill in ABILITA_LIST]

        for i in range(5):
            self.add_item(discord.ui.Select(
                placeholder=f"Punto Abilità {i+1}",
                options=abilita_options,
                custom_id=f"skill_{i}"
            ))

        self.add_item(discord.ui.Select(
            placeholder="Pregio (facoltativo)",
            options=[discord.SelectOption(label=tratto) for tratto in TRATTI_PREGI],
            min_values=0, max_values=1, custom_id="pregio"
        ))

        self.add_item(discord.ui.Select(
            placeholder="Difetto (solo per livello 3)",
            options=[discord.SelectOption(label=tratto) for tratto in TRATTI_DIFETTI],
            min_values=0, max_values=1, custom_id="difetto"
        ))

    async def on_submit(self, interaction: discord.Interaction):
        now = datetime.utcnow()
        nome_pg = self.pg["properties"]["Nome PG"]["rich_text"][0]["text"]["content"]
        livello = self.pg["properties"].get("Level", {}).get("number", 1)

        if livello >= 6:
            await interaction.response.send_message("❌ Questo personaggio è già al livello massimo.", ephemeral=True)
            return

        updates = {}
        conteggio = {}
        for item in self.children:
            if isinstance(item, discord.ui.Select) and item.custom_id and item.custom_id.startswith("skill_"):
                if item.values:
                    abilita = item.values[0]
                    conteggio[abilita] = conteggio.get(abilita, 0) + 1

        for abilita, aumento in conteggio.items():
            current = self.pg["properties"].get(abilita, {}).get("number", 0)
            updates[abilita] = {"number": current + aumento}

        livello_successivo = livello + 1
        updates["Level"] = {"number": livello_successivo}
        updates["Ultimo Level Up"] = {"date": {"start": now.date().isoformat()}}
        updates["Level Up"] = {"checkbox": False}
        updates["Role"] = {"number": 0}

        for item in self.children:
            if isinstance(item, discord.ui.Select):
                if item.custom_id == "pregio" and item.values:
                    updates["Tratto 7"] = {"multi_select": [{"name": item.values[0]}]}
                if item.custom_id == "difetto" and item.values and livello == 3:
                    updates["Tratto 8"] = {"multi_select": [{"name": item.values[0]}]}

        requests.patch(f"https://api.notion.com/v1/pages/{self.pg['id']}", headers=HEADERS, json={"properties": updates})

        await interaction.response.send_message(
            f"✅ **{nome_pg}** è salito al {INV_LIVELLI[livello_successivo]}!\nI punti abilità sono stati assegnati. Contatta lo staff per validare eventuali pregi/difetti.",
            ephemeral=True
        )

@tree.command(name="end", description="Concludi una role per un tuo PG")
async def end(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    res = requests.post(f"https://api.notion.com/v1/databases/{DATABASE_ID}/query", headers=HEADERS, json={
        "filter": {"property": "ID Discord", "rich_text": {"equals": user_id}}
    })
    pg_list = res.json().get("results", [])

    if not pg_list:
        await interaction.response.send_message("❌ Nessun personaggio associato.", ephemeral=True)
        return

    if len(pg_list) == 1:
        view = EndRoleSelect([
            discord.SelectOption(label=pg_list[0]["properties"]["Nome PG"]["rich_text"][0]["text"]["content"], value=pg_list[0]["id"])
        ], pg_list, interaction.user.id)
        await view.callback(interaction)
    else:
        await interaction.response.send_message("Seleziona il PG per registrare la giocata:", view=EndRoleView(pg_list, interaction.user.id), ephemeral=True)

####################### RUOTA ARCANA ##########################

ARCANI = {
    "L'Abisso": "Inverno",
    "Il Velo": "Inverno",
    "La Spiga": "Primavera",
    "Il Nodo": "Primavera",
    "Il Petalo": "Primavera",
    "La Lama": "Estate",
    "Il Pilastro": "Estate",
    "Il Giogo": "Estate",
    "L'Ombra": "Autunno",
    "L'Eco": "Autunno",
    "La Serpe": "Autunno",
    "La Cenere": "Inverno"
}

ARCANO_IMAGES = {
    "L'Abisso": "https://i.imgur.com/8iXPVpj.jpeg",
    "Il Velo": "https://i.imgur.com/u3HODrA.jpeg",
    "La Spiga": "https://i.imgur.com/8P4we0g.jpeg",
    "Il Nodo": "https://i.imgur.com/mHmKAqn.jpeg",
    "Il Petalo": "https://i.imgur.com/Wy9J7NX.jpeg",
    "La Lama": "https://i.imgur.com/CSzVlXs.jpeg",
    "Il Pilastro": "https://i.imgur.com/OYCjvXd.png",
    "Il Giogo": "https://i.imgur.com/Shhxmla.jpeg",
    "L'Ombra": "https://i.imgur.com/P4vbykp.jpeg",
    "L'Eco": "https://i.imgur.com/k3VAmoe.jpeg",
    "La Serpe": "https://i.imgur.com/o3lfIdf.jpeg",
    "La Cenere": "https://i.imgur.com/oLfN1b9.jpeg"
}

@tree.command(name="ruotaarcana", description="Gira la ruota degli Arcani e tenta la sorte!")
async def ruota_arcana(interaction: discord.Interaction):
    discord_id = str(interaction.user.id)
    url = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query"
    payload = {
        "filter": {
            "property": "ID Discord",
            "rich_text": {"equals": discord_id}
        }
    }

    try:
        res = requests.post(url, headers=HEADERS, json=payload)
        data = res.json()
    except Exception:
        await interaction.response.send_message("❌ Errore nel contattare il database.", ephemeral=True)
        return

    personaggi = data.get("results", [])
    if not personaggi:
        await interaction.response.send_message("❌ Nessun personaggio trovato associato al tuo ID.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)

    if len(personaggi) == 1:
        view = ScommessaView(personaggi[0], interaction.user.id)
        await interaction.followup.send("💫 Scegli quanto vuoi scommettere:", view=view, ephemeral=True)
    else:
        view = SelezionePG(interaction.user.id, personaggi)
        await interaction.followup.send(view=view, ephemeral=True)


class SelezionePG(discord.ui.View):
    def __init__(self, user_id, personaggi):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.mapping = {pg["properties"]["Nome PG"]["rich_text"][0]["text"]["content"]: pg for pg in personaggi}
        self.select = discord.ui.Select(
            placeholder="👤 Seleziona il tuo personaggio per giocare",
            options=[discord.SelectOption(label=nome, value=nome) for nome in self.mapping.keys()]
        )
        self.select.callback = self.callback
        self.add_item(self.select)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Non puoi usare questo menu.", ephemeral=True)
            return

        nome = self.select.values[0]
        pg = self.mapping[nome]
        view = ScommessaView(pg, self.user_id)
        await interaction.response.edit_message(content="💫 Scegli quanto vuoi scommettere:", view=view)


class ScommessaView(discord.ui.View):
    def __init__(self, pg, user_id):
        super().__init__(timeout=60)
        self.pg = pg
        self.user_id = user_id
        self.importo = 10

        self.select = discord.ui.Select(
            placeholder="Seleziona l'importo",
            options=[
                discord.SelectOption(label="10 Ȼ", value="10"),
                discord.SelectOption(label="20 Ȼ", value="20"),
                discord.SelectOption(label="50 Ȼ", value="50")
            ]
        )
        self.select.callback = self.select_callback
        self.add_item(self.select)

        self.scommetti_button = discord.ui.Button(label="Scommetti!", style=discord.ButtonStyle.success)
        self.scommetti_button.callback = self.scommetti
        self.add_item(self.scommetti_button)

    async def select_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Non puoi usare questo menu!", ephemeral=True)
            return
        self.importo = int(self.select.values[0])
        try:
            await interaction.response.defer()
        except discord.NotFound:
            return

    async def scommetti(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Questo bottone non è tuo!", ephemeral=True)
            return

        try:
            await interaction.response.defer(thinking=True)
        except discord.NotFound:
            return

        props = self.pg["properties"]
        nome_pg = props["Nome PG"]["rich_text"][0]["text"]["content"]
        segni_zodiacali = [normalizza(v["name"]) for v in props["Segno Zodiacale"]["multi_select"]]
        saldo = props["Croniri"].get("number", 0)
        scommessa = self.importo

        if saldo < scommessa:
            await interaction.followup.send(f"❌ {nome_pg} non ha abbastanza Croniri.", ephemeral=True)
            return

        nuovo_saldo = saldo - scommessa
        requests.patch(
            f"https://api.notion.com/v1/pages/{self.pg['id']}",
            headers=HEADERS,
            json={"properties": {"Croniri": {"number": nuovo_saldo}}}
        )

        estratto = random.choice(list(ARCANI.keys()))
        estratto_norm = normalizza(estratto)
        corrisponde = estratto_norm in segni_zodiacali
        stagionale = any(ARCANI.get(normalizza(s)) == ARCANI[estratto_norm] for s in segni_zodiacali)

        if corrisponde:
            vincita = scommessa * 3
            titolo = f"🎉 {nome_pg} ha scommesso {scommessa} Croniri alla Ruota degli Arcani"
            descrizione = f"L'Arcano **{estratto}** corrisponde al tuo segno! Hai vinto {vincita} Croniri!"
        elif stagionale:
            vincita = int(scommessa * 1.5)
            titolo = f"✨ {nome_pg} ha scommesso {scommessa} Croniri alla Ruota degli Arcani"
            descrizione = f"L'Arcano **{estratto}** è della stessa stagione del tuo segno. Hai vinto {vincita} Croniri!"
        else:
            vincita = 0
            titolo = f"💀 {nome_pg} ha scommesso {scommessa} Croniri alla Ruota degli Arcani"
            descrizione = f"L'Arcano estratto è **{estratto}**. Nessuna vincita. Hai perso la tua scommessa!"

        if vincita > 0:
            nuovo_saldo += vincita
            requests.patch(
                f"https://api.notion.com/v1/pages/{self.pg['id']}",
                headers=HEADERS,
                json={"properties": {"Croniri": {"number": nuovo_saldo}}}
            )

            tx_payload = {
                "parent": {"database_id": os.getenv("NOTION_TX_DB_ID")},
                "properties": {
                    "Data": {"date": {"start": datetime.utcnow().isoformat()}},
                    "Importo": {"number": vincita - scommessa},
                    "Causale": {"rich_text": [{"text": {"content": f"Ruota Arcana: puntata Ȼ{scommessa}, vincita Ȼ{vincita}"}}]},
                    "Mittente": {"relation": [{"id": self.pg["id"]}]}
                }
            }
            requests.post("https://api.notion.com/v1/pages", headers=HEADERS, json=tx_payload)

        embed = discord.Embed(title=titolo, description=descrizione, color=discord.Color.purple())
        embed.set_image(url=ARCANO_IMAGES.get(estratto, ""))

        await interaction.delete_original_response()
        await interaction.channel.send(embed=embed)

# === CROSTOLO DELLA FORTUNA ===

CROSTOLO_FRASES = [
    "Il cammino più semplice nasconde i sassi più acuminati.",
    "Attendi la marea: essa porta e toglie ciò che serve.",
    "Chi osserva senza fretta vede il vero disegno.",
    "Il tuo passo oggi incide il domani di altri.",
    "C'è luce anche in una stanza chiusa, se il cuore si apre.",
    "Ogni attesa ha un frutto. Anche la tua.",
    "Non parlare ora. L’ascolto è la chiave di questa giornata.",
    "Quel che ti sfugge, forse ti salva.",
    "Le parole giuste arrivano solo dopo il silenzio.",
    "Sii come l’inchiostro: silenzioso, ma indelebile.",
    "L’alba non è mai così lontana come sembra.",
    "Le chiavi che cerchi sono nella tua stessa tasca.",
    "Il vento che ti confonde ti sta anche spingendo.",
    "Fidati del dubbio: è lui che ha fatto nascere le stelle.",
    "Nel volto che eviti si nasconde una risposta.",
    "Oggi è un giorno che chiede attenzione, non azione.",
    "Nessuno sa cosa accadrà, ma tu sei pronto comunque.",
    "La verità ha mille maschere. Ne riconoscerai una.",
    "Sei già oltre il punto di svolta.",
    "Il tempo ti osserva. Non fare finta di nulla.",
    "Il suo sguardo è un portale verso tutto ciò che temevano chiamare amore.",
    "Due cuori danzano più silenziosamente di due piume in volo.",
    "Ti pensa quando cade il silenzio, e lì sei reale.",
    "Il tuo nome abita nelle sue preghiere non dette.",
    "Il destino ha scritto il vostro incontro con inchiostro rubato alla luna.",
    "Le sue mani ricordano il tuo volto meglio dello specchio.",
    "Non sa come dirtelo, ma ti ama come la notte ama il chiarore velato.",
    "Avete ballato in sogno? Allora è già reale.",
    "Ti attende, ogni giorno, nel punto esatto dove finisce il respiro.",
    "Il suo cuore batte una nota più forte quando ti nomina.",
    "L’amore vi cerca ogni volta che vi perdete.",
    "Ti ama nel modo in cui solo i fiori sanno amare il sole.",
    "I suoi pensieri ti vestono di seta ogni notte.",
    "Due anime si sono promesse molto prima di nascere.",
    "Ogni distanza fra voi è solo un attimo in ritardo.",
    "Ti sogna con la precisione di un cartografo perduto.",
    "Il tuo sorriso è la sua unica direzione.",
    "Ti ama come i poeti temono scrivere: troppo.",
    "Siete stati scritti sullo stesso foglio di destino.",
    "In un altro tempo, vi siete già scelti mille volte.",
    "Oggi una farfalla ti giudicherà. E avrà ragione.",
    "Una piuma cadrà davanti a te: non ignorarla.",
    "Gli idromuli stanno ridendo. Tu saprai perché domani.",
    "L’odore del rosmarino ti seguirà. È un avvertimento.",
    "Se sogni un corvo, digli che hai capito.",
    "Il tuo riflesso ha opinioni forti. Non contraddirlo oggi.",
    "Hai già parlato troppo con le ombre. È tempo di luce.",
    "Il tuo futuro sta dormendo in un vaso di terracotta.",
    "Le scale oggi potrebbero portarti altrove. Attento a salirle.",
    "Un sorriso falso ti rivelerà una verità autentica.",
    "Non fidarti del secondo cucchiaino. Il primo è complice.",
    "Il tuo respiro sa cose che la tua mente ancora ignora.",
    "Oggi il vento parla antico. Traduce solo chi ascolta col petto.",
    "Un sogno interrotto ti chiederà vendetta.",
    "Oggi una sedia vuota ti giudicherà.",
    "La tua ombra ha preso un impegno senza di te.",
    "Non attraversare tre archi di fila. Il quarto è trappola.",
    "Ti verrà in mente un nome mai sentito. Annotalo.",
    "Qualcosa di importante è nascosto dietro un rumore.",
    "Un petalo caduto oggi è un segno antico.",
    "Oggi il tuo passo pesa: qualcosa ti segue.",
    "Il tuo passato ha lasciato una lettera sotto il cuscino.",
    "Evita specchi storti. Riflettono intenzioni.",
    "Una voce fuori posto rivelerà la chiave.",
    "Non credere al profumo che ti attira: mente.",
    "Una parola detta per sbaglio sarà profezia.",
    "Oggi un animale ti guarderà troppo a lungo. Ringrazia.",
    "Il pavimento scricchiola per dire qualcosa.",
    "Dietro quella porta che eviti... c’è un te che non hai ancora conosciuto.",
    "Ogni tre respiri, pensa a chi hai dimenticato. Ti parlerà comunque.",
    "Oggi sei il protagonista del disastro. Bravo.",
    "La tua opinione è preziosa. Come un quadro rovesciato.",
    "Oggi non dire nulla. È meglio.",
    "Hai ragione. Ma solo nella tua personale commedia.",
    "Oggi sei il vaso di coccio in una sala piena di mechaelefanti. Buona fortuna.",
    "Continua così e sarai ricordato... come esempio da evitare.",
    "Se il silenzio è d’oro, oggi sei una miniera chiusa.",
    "Hai fatto del tuo meglio. Ed era meglio evitare.",
    "Sii te stesso. Ma non proprio adesso.",
    "Un genio silenzioso ti ha scelto. Poi ha cambiato idea.",
    "Parlare troppo ti ha portato qui. Complimenti.",
    "Hai chiesto un segno. Ignorerai anche questo.",
    "Siamo tutti destinati a qualcosa. Tu, probabilmente a ripetere l’errore.",
    "Ti giudicano? È il minimo.",
    "Il tuo piano ha un solo difetto: tutto.",
    "Hai vinto il premio per il miglior tentativo inutile.",
    "Non confondere intuizione con capriccio. Di nuovo.",
    "Sei sulla buona strada… per un pasticcio epocale.",
    "Ogni tua scelta oggi avrà effetti. Nessuno positivo.",
    "I tuoi silenzi gridano. Ma di solito sciocchezze.",
    "Non tutti i giorni puoi brillare. Oggi, ad esempio, sei opaco.",
    "La fortuna bussa. Tu però sei occupato a dire sciocchezze.",
    "Un consiglio? Fingiti saggio. È l’unica via.",
    "Oggi anche gli astri si sono girati dall’altra parte.",
    "Ridi pure. Ma sei tu la barzelletta.",
    "Oggi hai l’intuizione di una sedia vuota.",
    "Continua a provarci. Le catastrofi non si fanno da sole.",
    "Hai tutto il necessario per fallire con stile.",
    "Oggi persino il tuo riflesso ha alzato gli occhi al cielo.",
    "Sei un enigma. E nessuno vuole risolverlo.",
    "Sorpresa! Questo Crostolo non ha alcun significato mistico... ma ti becchi 500Ȼ. Contento?",
]

@tree.command(name="crostolo", description="Apri un Crostolo della Fortuna per un tuo personaggio!")
async def crostolo(interaction: discord.Interaction):
    discord_id = str(interaction.user.id)
    url = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query"
    payload = {"filter": {"property": "ID Discord", "rich_text": {"equals": discord_id}}}

    try:
        res = requests.post(url, headers=HEADERS, json=payload)
        data = res.json()
    except Exception:
        await interaction.response.send_message("❌ Errore nel contattare il database.", ephemeral=True)
        return

    personaggi = data.get("results", [])
    if not personaggi:
        await interaction.response.send_message("❌ Nessun PG trovato collegato al tuo ID Discord.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)

    if len(personaggi) == 1:
        await apri_crostolo(interaction, personaggi[0])
    else:
        class CrostoloPGView(discord.ui.View):
            def __init__(self, user_id):
                super().__init__(timeout=60)
                self.user_id = user_id
                self.mapping = {
                    pg["properties"]["Nome PG"]["rich_text"][0]["text"]["content"]: pg for pg in personaggi
                }
                self.select = discord.ui.Select(
                    placeholder="Seleziona il PG",
                    options=[discord.SelectOption(label=nome) for nome in self.mapping.keys()]
                )
                self.select.callback = self.callback
                self.add_item(self.select)

            async def callback(self, i: discord.Interaction):
                if i.user.id != self.user_id:
                    await i.response.send_message("Questo menu non è tuo!", ephemeral=True)
                    return
                nome = self.select.values[0]
                await i.response.defer()
                await apri_crostolo(interaction, self.mapping[nome])

        await interaction.followup.send("Scegli il personaggio per aprire il Crostolo:", view=CrostoloPGView(interaction.user.id), ephemeral=True)


async def apri_crostolo(interaction: discord.Interaction, pg):
    nome_pg = pg["properties"]["Nome PG"]["rich_text"][0]["text"]["content"]
    saldo = pg["properties"]["Croniri"]["number"]
    pg_id = pg["id"]

    if saldo < 5:
        await interaction.followup.send(f"❌ {nome_pg} non ha abbastanza Croniri (ne servono 5).", ephemeral=True)
        return

    nuovo_saldo = saldo - 5
    requests.patch(
        f"https://api.notion.com/v1/pages/{pg_id}",
        headers=HEADERS,
        json={"properties": {"Croniri": {"number": nuovo_saldo}}}
    )

    frase = random.choice(CROSTOLO_FRASES)
    vincita_speciale = 0

    if frase == "Sorpresa! Questo Crostolo non ha alcun significato mistico... ma ti becchi 500Ȼ. Contento?":
        vincita_speciale = 500
        nuovo_saldo += vincita_speciale
        requests.patch(
            f"https://api.notion.com/v1/pages/{pg_id}",
            headers=HEADERS,
            json={"properties": {"Croniri": {"number": nuovo_saldo}}}
        )
        requests.post("https://api.notion.com/v1/pages", headers=HEADERS, json={
            "parent": {"database_id": os.getenv("NOTION_TX_DB_ID")},
            "properties": {
                "Data": {"date": {"start": datetime.utcnow().isoformat()}},
                "Importo": {"number": vincita_speciale},
                "Causale": {"rich_text": [{"text": {"content": "Vincita Crostolo Speciale"}}]},
                "Mittente": {"relation": [{"id": pg_id}]}
            }
        })

    requests.post("https://api.notion.com/v1/pages", headers=HEADERS, json={
        "parent": {"database_id": os.getenv("NOTION_TX_DB_ID")},
        "properties": {
            "Data": {"date": {"start": datetime.utcnow().isoformat()}},
            "Importo": {"number": -5},
            "Causale": {"rich_text": [{"text": {"content": "Crostolo della Fortuna"}}]},
            "Mittente": {"relation": [{"id": pg_id}]}
        }
    })

    embed = discord.Embed(
        title=f"✨ {nome_pg} ha pagato 5Ȼ per un Crostolo della Fortuna!",
        description=f"*\"{frase}\"*",
        color=discord.Color.orange()
    )
    embed.set_image(url="https://i.imgur.com/yBEUHo4.jpeg")
    if vincita_speciale:
        embed.add_field(name="🏆 Premio Speciale", value=f"**+Ȼ500**", inline=False)

    await interaction.delete_original_response()
    await interaction.channel.send(embed=embed)

# CODICE PNG
@tree.command(name="png", description="Tira i dadi per un PNG di livello scelto")
async def png(interaction: discord.Interaction):
    view = PNGView(interaction.user.id)
    await interaction.response.send_message("🎲 Seleziona il livello del PNG:", view=view, ephemeral=True)

class PNGView(discord.ui.View):
    def __init__(self, user_id):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.select = discord.ui.Select(
            placeholder="Scegli il livello PNG",
            options=[
                discord.SelectOption(label="PNG Livello 1", description="3d10", value="1"),
                discord.SelectOption(label="PNG Livello 2", description="6d10", value="2"),
                discord.SelectOption(label="PNG Livello 3", description="9d10", value="3"),
                discord.SelectOption(label="PNG Livello 4", description="12d10", value="4"),
            ]
        )
        self.select.callback = self.select_callback
        self.add_item(self.select)

    async def select_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Questo menu non è tuo!", ephemeral=True)
            return

        livello = int(self.select.values[0])
        dadi = livello * 3
        tiri = [random.randint(1, 10) for _ in range(dadi)]

        successi = sum(1 for d in tiri if 7 <= d < 10) + sum(2 for d in tiri if d == 10)
        penalita = sum(1 for d in tiri if d == 1)
        netti = successi - penalita

        dettagli = [f"**{d}**" if d >= 7 else f"~~{d}~~" for d in tiri]

        if netti <= 0:
            esito = "💥 Fallimento critico!"
        elif netti >= 6:
            esito = "🚀 Successo critico!"
        elif netti >= 3:
            esito = "✅ Successo!"
        else:
            esito = "❌ Fallimento."

        embed = discord.Embed(
            title=f"🤖 Tiro PNG Livello {livello} ({dadi}d10)",
            description=(
                f"🎯 Risultati: [{', '.join(dettagli)}] → **{max(netti, 0)} Successi Netti**\n"
                f"{esito}"
            ),
            color=discord.Color.dark_teal()
        )

        await interaction.channel.send(embed=embed)



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
