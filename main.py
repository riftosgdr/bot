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

    # CODICE DADO:

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

MAPPING_CARATTERISTICHE = {c: c.upper() for c in CARATTERISTICHE}
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

        successi = sum(1 for d in tiri if d >= difficolta)
        dettagli = [f"**{d}**" if d >= difficolta else f"~~{d}~~" for d in tiri]

        if successi >= 6:
            esito = "🚀 Successo critico!"
        elif successi >= 1:
            esito = "✅ Successo!"
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

    # CODICE TRASFERIMENTO SOLDI:

@tree.command(name="trasferisci", description="Trasferisci Croniri da un tuo personaggio a un altro")
async def trasferisci(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    user_id = str(interaction.user.id)

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
            await inter.response.send_message("❌ Nessun destinatario disponibile.", ephemeral=True)
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
        await inter.response.send_message("Seleziona il destinatario:", view=view_dest, ephemeral=True)

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
        await interaction.response.defer(ephemeral=True, thinking=True)

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
        saldo_dest = res_dest.json()["properties"]["Croniri"]["number"] or 0
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
            f"💸 **{self.mittente_nome}** ha trasferito Ȼ{importo} a "
            f" **{self.destinatario_nome}**. (<@{interaction.user.id}>, <@{self.destinatario_user_id}>)\n"
            f"📄 Causale: {self.causale.value.strip()}"
        )

        await interaction.channel.send(messaggio_pubblico)

#GRATTA I SANTI

# Comando slash per Gratta i Santi
@tree.command(name="gratta", description="Tenta la fortuna con Gratta i Santi")
async def gratta(interaction: discord.Interaction):
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

    personaggi = data.get("results", [])
    if not personaggi:
        await interaction.followup.send("❌ Nessun PG trovato collegato al tuo ID Discord.", ephemeral=True)
        return

    if len(personaggi) == 1:
        pg = personaggi[0]
        view = GrattaSantiView(pg, interaction.user.id)
        await interaction.followup.send("🎰 Seleziona la puntata e gratta i santi!", view=view, ephemeral=True)
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

        await interaction.followup.send("Hai più di un PG. Scegli con quale giocare:", view=SelezionePG(interaction.user.id), ephemeral=True)


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
        await interaction.response.defer()

    async def submit(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Questo bottone non è tuo!", ephemeral=True)
            return

        await interaction.response.defer(thinking=True)

        nome_pg = self.pg["properties"]["Nome PG"]["rich_text"][0]["text"]["content"]
        saldo = self.pg["properties"]["Croniri"]["number"] or 0
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
            else:
                moltiplicatore = 0
                messaggio = "❌ Ritenta! Sarai più fortunato!"

        vincita = int(puntata * moltiplicatore)

        if vincita > 0:
            nuovo_saldo += vincita
            requests.patch(
                f"https://api.notion.com/v1/pages/{self.pg['id']}",
                headers=HEADERS,
                json={"properties": {"Croniri": {"number": nuovo_saldo}}}
            )
            requests.post("https://api.notion.com/v1/pages", headers=HEADERS, json={
                "parent": {"database_id": os.getenv("NOTION_TX_DB_ID")},
                "properties": {
                    "Data": {"date": {"start": datetime.utcnow().isoformat()}},
                    "Importo": {"number": vincita},
                    "Causale": {"rich_text": [{"text": {"content": f"Vincita grattaisanti da {nome_pg}"}}]},
                    "Destinatario": {"relation": [{"id": self.pg["id"]}]}
                }
            })

        requests.post("https://api.notion.com/v1/pages", headers=HEADERS, json={
            "parent": {"database_id": os.getenv("NOTION_TX_DB_ID")},
            "properties": {
                "Data": {"date": {"start": datetime.utcnow().isoformat()}},
                "Importo": {"number": -puntata},
                "Causale": {"rich_text": [{"text": {"content": f"Puntata grattaisanti da {nome_pg}"}}]},
                "Mittente": {"relation": [{"id": self.pg["id"]}]},
                "Destinatario": {"rich_text": [{"text": {"content": "Gratta i Santi"}}]}
            }
        })

        embed = discord.Embed(title=f"🎫 {nome_pg} ha grattato i Santi!", color=discord.Color.gold())
        embed.add_field(name="🧩 Santi Estratti:", value=" | ".join(nomi), inline=False)
        embed.add_field(name="🎯 Esito:", value=messaggio, inline=False)
        embed.add_field(name="💰 Puntata:", value=f"Ȼ{puntata}", inline=True)
        embed.add_field(name="🏆 Vincita:", value=f"Ȼ{vincita}", inline=True)
        embed.set_image(url="https://i.imgur.com/gxUgDqz.jpeg")

await interaction.followup.send(embed=embed, ephemeral=False)

# === LIVELLAMENTO PG ===

ABILITA_LIST = [
    "Atletica", "Mira", "Combattimento", "Riflessi", "Robustezza",
    "Analisi", "Osservare", "Studio", "Cultura", "Tecnica",
    "Autocontrollo", "Persuasione", "Comando", "Maschera", "Intimidazione",
    "Conoscenza", "Trasmutazione", "Resilienza", "Salto"
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
