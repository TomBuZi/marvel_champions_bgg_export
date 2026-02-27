import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd

# Daten laden (basierend auf deinen Dateien)
# Ich erstelle hier DataFrames aus den hochgeladenen CSVs

# 1. Helden Total
df_heroes = pd.read_csv('heroes_total.csv', sep=';')
df_heroes = df_heroes.sort_values('Count', ascending=False).head(10) # Top 10

# 2. Aspekt Statistik
df_aspects = pd.read_csv('marvel_champions_aspect_stats.csv', sep=';')
# Bereinigen von Leerzeichen, falls vorhanden
df_aspects['aspect'] = df_aspects['aspect'].str.strip()

# 3. Szenario Statistik
df_scenarios = pd.read_csv('marvel_champions_scenario_stats.csv', sep=';')
df_scenarios = df_scenarios.sort_values('count', ascending=False).head(10) # Top 10

# 4. Plays (für Win/Loss)
df_plays = pd.read_csv('marvel_champions_plays.csv', sep=';')

# 5. Helden & Aspekte Kombinationen
df_hero_aspects = pd.read_csv('heroes_aspects.csv', sep=';')

# --- GRAFIK SETTINGS ---
sns.set_style("whitegrid")
plt.rcParams.update({'font.size': 10})
marvel_colors = ['#E62429', '#202020', '#F0F0F0', '#FFB700'] # Rot, Schwarz, Weiß, Gold (Marvel Style)

# Aspekt Farben (Thematisch passend zum Spiel)
aspect_colors = {
    'Aggression': '#C8102E', # Rot
    'Protection': '#00A651', # Grün
    'Justice': '#FFD700',    # Gelb/Gold
    'Leadership': '#0072CE', # Blau
    'Basic': '#808080',      # Grau
    'Precon': '#A0A0A0',
    "'Pool": '#FF69B4'       # Pink
}

# --- PLOTTING ---

fig, axes = plt.subplots(3, 2, figsize=(16, 20))
plt.subplots_adjust(hspace=0.4, wspace=0.3)

# 1. TOP 10 HELDEN (Bar Chart)
sns.barplot(ax=axes[0, 0], x='Count', y='Hero', data=df_heroes, palette="rocket")
axes[0, 0].set_title('Top 10 Meistgespielte Helden', fontsize=14, fontweight='bold')
axes[0, 0].set_xlabel('Anzahl Spiele')
axes[0, 0].set_ylabel('')

# 2. ASPEKT VERTEILUNG (Donut Chart)
# Farben zuordnen
colors = [aspect_colors.get(x, '#333333') for x in df_aspects['aspect']]
wedges, texts, autotexts = axes[0, 1].pie(df_aspects['count'], labels=df_aspects['aspect'], 
                                          autopct='%1.1f%%', startangle=90, colors=colors, pctdistance=0.85)
# Kreis in die Mitte für Donut-Effekt
centre_circle = plt.Circle((0,0),0.70,fc='white')
axes[0, 1].add_artist(centre_circle)
axes[0, 1].set_title('Verteilung der Aspekte', fontsize=14, fontweight='bold')
for text in texts: text.set_fontsize(9)
for autotext in autotexts: autotext.set_color('white') if autotext.get_text() != 'Basic' else autotext.set_color('black')

# 3. TOP 10 SZENARIEN (Bar Chart)
sns.barplot(ax=axes[1, 0], x='count', y='scenario', data=df_scenarios, palette="mako")
axes[1, 0].set_title('Top 10 Meistgespielte Szenarien', fontsize=14, fontweight='bold')
axes[1, 0].set_xlabel('Anzahl Spiele')
axes[1, 0].set_ylabel('')

# 4. GEWINNRATE (Pie Chart)
win_loss = df_plays['result'].value_counts()
# Nur 'won' und 'lost' berücksichtigen (Leerzeichen bereinigen)
if 'won' in win_loss.index and 'lost' in win_loss.index:
    subset = win_loss[['won', 'lost']]
    axes[1, 1].pie(subset, labels=['Gewonnen', 'Verloren'], autopct='%1.1f%%', 
                   colors=['#4CAF50', '#F44336'], startangle=90, explode=(0.05, 0))
    axes[1, 1].set_title('Gesamt Gewinnrate', fontsize=14, fontweight='bold')
else:
    axes[1, 1].text(0.5, 0.5, 'Keine eindeutigen Win/Loss Daten', ha='center')

# 5. HELDEN & ASPEKTE (Stacked Bar für Top 5 Helden)
top_5_heroes_list = df_heroes['Hero'].head(5).tolist()
df_top_aspects = df_hero_aspects[df_hero_aspects['Hero'].isin(top_5_heroes_list)]
# Pivot für Stacked Bar
df_pivot = df_top_aspects.pivot(index='Hero', columns='Aspect', values='Count').fillna(0)
# Sortieren nach Total
df_pivot['total'] = df_pivot.sum(axis=1)
df_pivot = df_pivot.sort_values('total', ascending=False).drop('total', axis=1)

# Plotten
df_pivot.plot(kind='bar', stacked=True, ax=axes[2, 0], 
              color=[aspect_colors.get(x, '#333333') for x in df_pivot.columns])
axes[2, 0].set_title('Aspekt-Präferenz der Top 5 Helden', fontsize=14, fontweight='bold')
axes[2, 0].set_xlabel('')
axes[2, 0].set_ylabel('Anzahl Spiele')
axes[2, 0].legend(title='Aspekt', bbox_to_anchor=(1.05, 1), loc='upper left')

# 6. SPIELE ÜBER ZEIT (Line Chart - Monatlich)
# Datum konvertieren
df_plays['date'] = pd.to_datetime(df_plays['date'])
plays_per_month = df_plays.resample('ME', on='date').size()

if not plays_per_month.empty:
    axes[2, 1].plot(plays_per_month.index, plays_per_month.values, marker='o', color='#E62429', linewidth=2)
    axes[2, 1].set_title('Spielaktivität über die Zeit', fontsize=14, fontweight='bold')
    axes[2, 1].set_ylabel('Spiele pro Monat')
    axes[2, 1].grid(True, which='both', linestyle='--', linewidth=0.5)
else:
    axes[2, 1].text(0.5, 0.5, 'Keine Zeitdaten verfügbar', ha='center')

plt.tight_layout()
plt.show()