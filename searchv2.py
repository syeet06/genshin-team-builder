import google.generativeai as genai
import json

API_KEY = '' 

genai.configure(api_key=API_KEY)

model = genai.GenerativeModel("gemini-2.0-flash")

async def explain_teams(teams): 
    character_data_path='characters.json'
    try:
        with open(character_data_path, 'r', encoding='utf-8') as f:
            character_data = json.load(f)
    except FileNotFoundError:
        print(f"Error: Character data file '{character_data_path}' not found.")
        return None  
    except json.JSONDecodeError:
        print(f"Error: Invalid JSON format in '{character_data_path}'.")
        return None

    team_text = ""
    for team in teams:
        formatted_team_key = ", ".join(
            f"{char['Name']} ({char['Role']})" for char in team['Characters']
        )
        
        team_text += f"**Team Explanation Start**\nTEAM: {formatted_team_key}\nExplanation:\n"
        for char in team['Characters']:
            char_name = char['Name']
            char_data = character_data.get(char_name.strip())

            if char_data:
                team_text += f" - {char_name} (Role: {char['Role']}, Element: {char['Element']}, Tier: {char['Tier']})\n"
                team_text += f"    - Elemental Skill: {char_data.get('elemental_skill', 'N/A')}\n"
                team_text += f"    - Elemental Burst: {char_data.get('elemental_burst', 'N/A')}\n"
                team_text += f"    - Artifact Set: {char_data.get('best_artifact_set', 'N/A')}\n"
            else:
                team_text += f" - {char_name} (Data not found!)\n"

    prompt = f'''
        You are an expert Genshin Impact team strategist. Based solely on the given team composition and character details, generate a structured explanation that covers elemental synergies, valid playstyles, role distribution, resource management (based on characters' energy requirements), a funny overall judgement on the team and optimal artifact sets. Keep the explanation for each team roughly the same length.

        Guidelines:
        1. Allowed reactions (DO NOT mix up these reactions.):
        - Vaporize = Hydro + Pyro
        - Freeze = Cryo + Hydro
        - Melt = Cryo + Pyro
        - Burning = Dendro + Pyro 
        - Bloom = Dendro + Hydro
        - Quicken = Dendro + Electro
        - Hyperbloom = Electro + Dendro + Hydro. If this occurs, bloom or quicken should not be mentioned.
        - Burgeon = Pyro + Dendro + Hydro 
        - Electro-Charged = Hydro + Electro
        - Overload = Pyro + Electro
        - Swirl = triggered only with Pyro/Hydro/Electro/Cryo
        - Crystallize = triggered only with Pyro/Hydro/Electro/Cryo
        2. The following is an example explanation generation:
        (GENERATE ALL TEAMS LIKE THIS, and always start with Team 1)**Team 1: Mavuika (Main DPS), Citlali (Sub-DPS), Xilonen (Support), Bennett (Support)** 
        Both Citlali and Xilonen gain and lose Nightsoul points so quickly, allowing Mavuika to continuously cast her Elemental Burst with ease. Bennett provides healing and ATK buff through his Burst.

        Role distribution: Citlali is a notable off-field Cryo driver who can help Mavuika continuously trigger Melt on most of her attacks. On top of that, Citlali reduces enemies’ resistance to Pyro by 20% through her Ascension passive. Let Xilonen take the field for a few seconds and shred enemies' RES, allowing your attacks to deal more manage.

        Resource management: Fighting Spirit generation is crucial for Mavuika, but that is not an issue with both Citlali and Xilonen, who both have Nightsoul, in the team.
        
        Overall, this is an extremely good team which should serve you well in both the abyss and the overworld. Are you sure you aren't a whale?
        
        Recommended artifact set: Mavuika (Obsidian Codex), Citlali (Scroll of the Hero of Cinder City), Xilonen (Scroll of the Hero of Cinder City), Bennett (Noblesse Oblige)

        Teams for Analysis:
        {team_text}
        '''


    response = model.generate_content(prompt) 

    print(response.text)
    return response.text

