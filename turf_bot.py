import os
import asyncio
import discord
from discord.ext import commands

# ===================
# Setup
# ===================

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)

events = {}
last_fight_event = None
LOGO_URL = "https://cdn.discordapp.com/attachments/1416457141740503050/1416457187428925510/skandinavien_tribe.png"

# ===================
# Embeds
# ===================

def build_announce_embed(event_type, desc, participants):
    if event_type == "fight":
        title = "# 🥊 FIGHT"
        color = discord.Color.red()
    else:
        title = "# 🧭 AUFSTELLUNG"
        color = discord.Color.blurple()

    description = (
        "# ✨ TRAGE DICH INS TURF EIN! ✨\n\n"
        f"__**{desc}**__\n\n"
        "✅ Drücke unten auf den Button, um dich einzutragen!"
    )

    embed = discord.Embed(title=title, description=description, color=color)
    if participants:
        names = "\n".join([f"• <@{uid}>" for uid in participants])
        embed.add_field(name=f"✅ Teilnehmer ({len(participants)})", value=names, inline=False)
    else:
        embed.add_field(name="✅ Teilnehmer (0)", value="Noch keine Teilnehmer.", inline=False)
    embed.set_image(url=LOGO_URL)
    return embed


def build_einteilung_embed(desc, participants, categories):
    description = (
        "# 🥊 FIGHT – EINTEILUNG\n\n"
        f"__**{desc}**__\n\n"
        "Admins können hier die Spieler zuordnen ⬇️"
    )
    embed = discord.Embed(description=description, color=discord.Color.orange())
    if participants:
        names = "\n".join([f"• <@{uid}>" for uid in participants])
        embed.add_field(name=f"✅ Alle Teilnehmer ({len(participants)})", value=names, inline=False)
    else:
        embed.add_field(name="✅ Alle Teilnehmer (0)", value="Noch keine Teilnehmer.", inline=False)
    for cat in ["Masse", "Anti", "Freestyle"]:
        val = "\n".join([f"• <@{uid}>" for uid in categories[cat]]) if categories[cat] else "—"
        embed.add_field(name=f"🎯 {cat}", value=val, inline=True)
    embed.set_image(url=LOGO_URL)
    return embed

# ===================
# Update & Auto-Delete
# ===================

async def update_announce(msg_id, guild):
    if msg_id not in events:
        return
    data = events[msg_id]
    ch = guild.get_channel(data["announce_channel"])
    try:
        msg = await ch.fetch_message(msg_id)
        embed = build_announce_embed(data["type"], data["desc"], data["participants"])
        await msg.edit(embed=embed, view=AnnounceView(msg_id))
    except Exception as e:
        print(f"[UPDATE ANNOUNCE ERROR] {e}")


async def update_einteilung(msg_id, guild):
    if msg_id not in events:
        return
    data = events[msg_id]
    if "einteil_channel" not in data or "einteil_msg" not in data:
        return
    try:
        ch = guild.get_channel(data["einteil_channel"])
        msg = await ch.fetch_message(data["einteil_msg"])
        embed = build_einteilung_embed(data["desc"], data["participants"], data["categories"])
        await msg.edit(embed=embed, view=EinteilungView(msg_id, guild))
    except Exception as e:
        print(f"[UPDATE EINTEILUNG ERROR] {e}")


async def auto_delete(msg_id, guild, delay):
    await asyncio.sleep(delay)
    if msg_id not in events:
        return
    data = events.pop(msg_id)
    try:
        ch = guild.get_channel(data["announce_channel"])
        msg = await ch.fetch_message(msg_id)
        await msg.delete()
    except:
        pass
    if "einteil_channel" in data and "einteil_msg" in data:
        try:
            ch = guild.get_channel(data["einteil_channel"])
            msg = await ch.fetch_message(data["einteil_msg"])
            await msg.delete()
        except:
            pass

# ===================
# Views
# ===================

class AnnounceView(discord.ui.View):
    def __init__(self, msg_id):
        super().__init__(timeout=None)
        self.msg_id = msg_id

    @discord.ui.button(label="Ich bin dabei!", style=discord.ButtonStyle.success, emoji="✅")
    async def join(self, interaction, button):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        events[self.msg_id]["participants"].add(interaction.user.id)
        await update_announce(self.msg_id, guild)
        await update_einteilung(self.msg_id, guild)
        await interaction.followup.send("✅ Du bist eingetragen!", ephemeral=True)

    @discord.ui.button(label="Austragen", style=discord.ButtonStyle.danger, emoji="❌")
    async def leave(self, interaction, button):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        events[self.msg_id]["participants"].discard(interaction.user.id)
        for cat in events[self.msg_id]["categories"].values():
            cat.discard(interaction.user.id)
        await update_announce(self.msg_id, guild)
        await update_einteilung(self.msg_id, guild)
        await interaction.followup.send("❌ Du bist ausgetragen!", ephemeral=True)

    @discord.ui.button(label="Event löschen", style=discord.ButtonStyle.secondary, emoji="🗑️")
    async def delete(self, interaction, button):
        await interaction.response.defer(ephemeral=True)
        if not interaction.user.guild_permissions.administrator:
            await interaction.followup.send("Nur Admins können Events löschen.", ephemeral=True)
            return
        await auto_delete(self.msg_id, interaction.guild, 0)
        await interaction.followup.send("🗑️ Event gelöscht!", ephemeral=True)


class CategorySelect(discord.ui.Select):
    def __init__(self, msg_id, category, guild):
        self.msg_id = msg_id
        self.category = category
        options = []
        for uid in events[msg_id]["participants"]:
            member = guild.get_member(uid)
            label = member.display_name if member else f"User {uid}"
            options.append(discord.SelectOption(label=label, value=str(uid)))
        if not options:
            options = [discord.SelectOption(label="(Keine Teilnehmer)", value="none", default=True)]
        super().__init__(placeholder=f"{category} zuweisen …",
                         min_values=0, max_values=len(options), options=options)

    async def callback(self, interaction):
        await interaction.response.defer(ephemeral=True)
        if not interaction.user.guild_permissions.administrator:
            await interaction.followup.send("Nur Admins dürfen einteilen.", ephemeral=True)
            return
        if "none" in self.values:
            return
        for cat in events[self.msg_id]["categories"].values():
            for uid in self.values:
                cat.discard(int(uid))
        for uid in self.values:
            events[self.msg_id]["categories"][self.category].add(int(uid))
        await update_einteilung(self.msg_id, interaction.guild)
        await interaction.followup.send(f"✅ Zugewiesen zu {self.category}", ephemeral=True)


class EinteilungView(discord.ui.View):
    def __init__(self, msg_id, guild):
        super().__init__(timeout=None)
        self.add_item(CategorySelect(msg_id, "Masse", guild))
        self.add_item(CategorySelect(msg_id, "Anti", guild))
        self.add_item(CategorySelect(msg_id, "Freestyle", guild))

# ===================
# Commands
# ===================

@bot.tree.command(name="announce", description="Starte ein Turf-Event")
async def announce(interaction: discord.Interaction):
    class EventTypeDropdown(discord.ui.Select):
        def __init__(self):
            options = [
                discord.SelectOption(label="Fight", emoji="🥊", value="fight"),
                discord.SelectOption(label="Aufstellung", emoji="🧭", value="aufstellung")
            ]
            super().__init__(placeholder="Event-Typ wählen …", options=options, min_values=1, max_values=1)

        async def callback(self, inter: discord.Interaction):
            event_type = self.values[0]

            class DescModal(discord.ui.Modal, title="Beschreibung eingeben"):
                desc = discord.ui.TextInput(label="Beschreibung", style=discord.TextStyle.paragraph)

                async def on_submit(self, inter2: discord.Interaction):
                    class ChannelSelect(discord.ui.Select):
                        def __init__(self):
                            channels = [
                                discord.SelectOption(label=c.name, value=str(c.id))
                                for c in inter.guild.text_channels
                            ]
                            super().__init__(placeholder="Channel wählen …", options=channels, min_values=1, max_values=1)

                        async def callback(self2, inter3: discord.Interaction):
                            await inter3.response.defer(ephemeral=True)
                            ch = inter.guild.get_channel(int(self2.values[0]))
                            embed = build_announce_embed(event_type, str(self.desc), set())
                            msg = await ch.send(embed=embed)
                            msg_id = msg.id

                            events[msg_id] = {
                                "type": event_type,
                                "desc": str(self.desc),
                                "participants": set(),
                                "announce_channel": ch.id,
                                "categories": {"Masse": set(), "Anti": set(), "Freestyle": set()}
                            }
                            await msg.edit(view=AnnounceView(msg_id))

                            global last_fight_event
                            if event_type == "fight":
                                last_fight_event = msg_id

                            delay = 60*60*12 if event_type == "fight" else 60*60*24
                            bot.loop.create_task(auto_delete(msg_id, inter.guild, delay))
                            await inter3.followup.send(f"{event_type.upper()}-Event gestartet ✅", ephemeral=True)

                    await inter2.response.send_message("Channel auswählen:", view=discord.ui.View().add_item(ChannelSelect()), ephemeral=True)

            await inter.response.send_modal(DescModal())

    view = discord.ui.View()
    view.add_item(EventTypeDropdown())
    await interaction.response.send_message("Bitte Event-Typ auswählen:", view=view, ephemeral=True)


@bot.tree.command(name="einteilung", description="Starte die Einteilung für das letzte Fight-Event")
async def einteilung(interaction: discord.Interaction):
    global last_fight_event
    if not last_fight_event or last_fight_event not in events:
        await interaction.response.send_message("⚠️ Kein aktives Fight-Event gefunden.", ephemeral=True)
        return

    class ChannelSelect(discord.ui.Select):
        def __init__(self):
            channels = [
                discord.SelectOption(label=c.name, value=str(c.id))
                for c in interaction.guild.text_channels
            ]
            super().__init__(placeholder="Einteilungs-Channel wählen …", options=channels, min_values=1, max_values=1)

        async def callback(self, inter: discord.Interaction):
            await inter.response.defer(ephemeral=True)
            ch = interaction.guild.get_channel(int(self.values[0]))
            data = events[last_fight_event]
            embed = build_einteilung_embed(data["desc"], data["participants"], data["categories"])
            ein_msg = await ch.send(embed=embed, view=EinteilungView(last_fight_event, interaction.guild))
            events[last_fight_event]["einteil_channel"] = ch.id
            events[last_fight_event]["einteil_msg"] = ein_msg.id
            await inter.followup.send("Einteilung gestartet ✅", ephemeral=True)

    view = discord.ui.View()
    view.add_item(ChannelSelect())
    await interaction.response.send_message("Bitte Einteilungs-Channel wählen:", view=view, ephemeral=True)

# ===================
# Startup
# ===================

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"{bot.user} ist online!")

bot.run(os.getenv("DISCORD_TOKEN"))
