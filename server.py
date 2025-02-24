import genshin
from fastapi import FastAPI, HTTPException, Request 
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import genshin
import pandas as pd
import json 
import time
from itertools import combinations
from searchv2 import explain_teams
from fastapi.staticfiles import StaticFiles

start= time.time()

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class HoYoLABLoginRequest(BaseModel):
    username: str
    password: str

cookies = {}

@app.post("/hoyolab_login")
async def hoyolab_login(request: HoYoLABLoginRequest):
    try:
        client = genshin.Client()
        login_cookies = await client.login_with_password(request.username, request.password)
        ltuid_v2 = login_cookies.ltuid_v2 if hasattr(login_cookies, 'ltuid_v2') else None
        ltoken_v2 = login_cookies.ltoken_v2 if hasattr(login_cookies, 'ltoken_v2') else None
        ltmid_v2 = login_cookies.ltmid_v2 if hasattr(login_cookies, 'ltmid_v2') else None
        cookies['ltuid_v2'] = ltuid_v2
        cookies['ltoken_v2'] = ltoken_v2
        cookies['ltmid_v2'] = ltmid_v2

        print(cookies)
        return cookies

    except genshin.errors.InvalidCookies:
        raise HTTPException(status_code=401, detail="Invalid login credentials.")
    except Exception as e:
        print(f"Error occurred: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

def normalise(name):
    return name.replace(" ", "-")

@app.get("/get_characters")
async def get_characters():
    try:
        with open('cached_characters.json', 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        # Fetch if no cache
        client = genshin.Client(cookies)
        characters = await client.get_calculator_characters(sync=True)
        character_names = [char.name for char in characters]
        with open('cached_characters.json', 'w') as f:
            json.dump(character_names, f)
        return character_names



def load_character_data():
    df = pd.read_csv('actual.csv')
    if df['Character'].duplicated().any():
        raise ValueError("Duplicate characters found")

    
    df['Best Role'] = df['Best Role'].str.split('/')  
    character_data = df.set_index('Character')[['Best Role', 'Role Tier', 'Element', 'Nightsoul','Off-field']].to_dict(orient='index')
    
    for char in character_data:
        character_data[char]['roles'] = character_data[char]['Best Role']
        character_data[char]['tier'] = character_data[char]['Role Tier']
        character_data[char]['element'] = character_data[char]['Element']
        character_data[char]['nightsoul'] = character_data[char]['Nightsoul']
        character_data[char]['off_field'] = str(character_data[char]['Off-field']).strip().upper() == "TRUE"
        del character_data[char]['Best Role']
        del character_data[char]['Role Tier']
        del character_data[char]['Element']
        del character_data[char]['Nightsoul']
        del character_data[char]['Off-field']

    return character_data

def expand_traveler_variants(user_characters, character_data):
    traveler_variants = [
        'Traveler-Anemo',
        'Traveler-Geo',
        'Traveler-Electro',
        'Traveler-Dendro',
        'Traveler-Hydro',
        'Traveler-Pyro'
    ]
    new_characters = []
    for char in user_characters:
        if char == 'Traveler':
            new_characters.extend(traveler_variants)
        else:
            new_characters.append(char)
    return new_characters



def tier_sort(character_list, character_data):
    tier_order = {"SS": 100, "S": 80, "A": 50, "B": 20, "C": 10}
    return sorted(character_list, key=lambda char: tier_order[character_data[char]['tier']], reverse=True)

def calculate_resonance_score(team_elements, team, char_cache):
        element_counts = {}
        score = 0 
        for element in team_elements:
            element_counts[element] = element_counts.get(element, 0) + 1
        for char in team: #character specific support
            if char == 'Fischl': #fischl not the best in hyperbloom
                    hydro = element_counts.get('Hydro',0)
                    dendro = element_counts.get('Dendro',0)
                    if hydro + dendro >= 2:
                        score-=20 
            if 'Support' in char_cache[char]['roles']:
                # Chev needs Pyro/Electro teammates
                if char == 'Chevreuse':
                    pyro = element_counts.get('Pyro', 0)
                    electro = element_counts.get('Electro', 0)
                    if pyro + electro < 3:
                        score -= 50  
                        
                # Sara needs Electro DPS
                elif char == 'Kujou Sara':
                    if element_counts.get('Electro', 0) < 2:
                        score -= 100
                
                # Shenhe is a cryo support 
                elif char == 'Shenhe':
                    if element_counts.get('Cryo', 0) < 2:
                        score -= 100
                
                elif char == 'Faruzan':
                    if element_counts.get('Anemo', 0) < 2:
                        score -= 100
                
                elif char == 'Gorou':
                    if element_counts.get('Geo', 0) < 2:
                        score -= 100

                elif char == 'Kuki Shinobu': #prioritize kuki over other electro supports like fischl in hyperbloom teams
                    hydro = element_counts.get('Hydro',0)
                    dendro = element_counts.get('Dendro',0)
                    if hydro + dendro >= 2:
                        score+=100


                
        
        pyro_count = element_counts.get("Pyro", 0)
        hydro_count = element_counts.get("Hydro", 0)
        cryo_count = element_counts.get("Cryo", 0)
        electro_count = element_counts.get("Electro", 0)
        geo_count = element_counts.get("Geo", 0)
        anemo_count = element_counts.get("Anemo", 0)
        dendro_count = element_counts.get("Dendro", 0)
        
        #Resonances 
        if pyro_count >= 2: score += 20
        if hydro_count >= 2: score += 15
        if cryo_count >= 2: score += 20
        if electro_count >= 2: score += 15
        if geo_count >= 2: score += 15
        if anemo_count >= 2: score += 10
        if dendro_count >= 2: score += 15

        #Reactions
        if hydro_count and pyro_count: score += 25  # Vaporize
        if cryo_count and pyro_count: score += 30   # Melt
        if cryo_count and hydro_count: score += 8  # Freeze
        if electro_count and pyro_count: score += 15  # Overload
        dendro_off_field = any(
            char_cache[char]['element'] == 'Dendro' and char_cache[char].get('off_field', True)
            for char in team
    )
        if electro_count and hydro_count and dendro_off_field and pyro_count==0: score += 60  #hyperbloom
        if hydro_count and dendro_count and pyro_count: score += 20 #burgeon 
        if hydro_count and dendro_count: score +=15 #bloom 
        if electro_count and dendro_count: score+=8 #quicken

        if geo_count and (hydro_count or pyro_count or electro_count): #crystallise 
            score +=5
        
        if anemo_count and (hydro_count or pyro_count or electro_count): #swirl
            score += 15
        if anemo_count and (geo_count or dendro_count):
            score -= 15
            
        return score



# generate teams 
def generate_teams_optimized(user_characters, character_data, num_teams, max_teams_per_dps):
    expanded_characters = expand_traveler_variants(user_characters, character_data)
    print(expanded_characters)
    
    INCOMPATIBLE_SUPPORTS = {
        'Alhaitham': ['Bennett', 'Kaedehara-Kazuha', 'Xiangling'],
        'Hu-Tao': ['Bennett'],
        'Neuvillette': ['Bennett'],
        'Lyney': ['Xingqiu', 'Yelan'],
        'Tighnari': ['Xiangling'],
        'Mavuika': ['Xiangling']
    }
    char_cache = {}
    char_elements = {}
    char_nightsoul = {}
    main_dps_usage = {}
    
    for char in expanded_characters:
        if char not in character_data:
            continue
        
        info = character_data[char]
        roles = info['roles']
        tier = info['tier']
        element = info['element']
        nightsoul = info['nightsoul']
        off_field = info['off_field']
        tier_value = {"SS": 100, "S": 80, "A": 50, "B": 20, "C": 10}[tier]
        
        char_cache[char] = {
            'roles': set(roles),
            'element': element,
            'nightsoul': nightsoul,
            'tier_value': tier_value,
            'off_field': off_field,  
            'is_main_dps': 'Main DPS' in roles,
            'is_sub_dps': 'Sub-DPS' in roles,
            'is_support': 'Support' in roles
        }

        char_elements[char] = element
        char_nightsoul[char] = nightsoul
        if char_cache[char]['is_main_dps']:
            main_dps_usage[char] = 0

    role_chars = {
        'Main DPS': [char for char in char_cache if char_cache[char]['is_main_dps']],
        'Sub-DPS': [char for char in char_cache if char_cache[char]['is_sub_dps']],
        'Support': [char for char in char_cache if char_cache[char]['is_support']]
    }
    for role in role_chars:
        role_chars[role].sort(key=lambda x: char_cache[x]['tier_value'], reverse=True)
    
    def calculate_off_field_bonus(team):
        off_field_count = sum(1 for char in team if char_cache[char].get('off_field', False))
        bonus = 0
        if off_field_count == 2:
            bonus = 10  
        elif off_field_count == 3:
            bonus = 15
        return bonus
    
    def calculate_nightsoul_score(team):
        nightsoul_count = sum(1 for char in team if char_nightsoul[char])
        if nightsoul_count == 4:
            return 20
        elif nightsoul_count == 3:
            return 15
        elif nightsoul_count >= 2:
            return 10
        return 0

    def calculate_team_score(team):
        elements = [char_cache[char]['element'] for char in team]
        base_score = sum(char_cache[char]['tier_value'] for char in team)
        resonance_score = calculate_resonance_score(elements, team, char_cache)
        nightsoul_score = calculate_nightsoul_score(team)
        off_field_bonus = calculate_off_field_bonus(team)
        return base_score + resonance_score + nightsoul_score + off_field_bonus

    seen_teams = set()
    def is_unique_team(team):
        team_key = tuple(sorted(char.replace('Traveler-', 'Traveler') for char in team))
        if team_key in seen_teams:
            return False
        seen_teams.add(team_key)
        return True

    collected_teams = []
    
    for main in role_chars['Main DPS']:
        teams_for_main = []
        sub_candidates = [char for char in role_chars['Sub-DPS'] if char != main]
        incompatible = INCOMPATIBLE_SUPPORTS.get(main, [])
        sub_candidates = [char for char in role_chars['Sub-DPS'] if char != main and char not in incompatible]
        support_candidates = [char for char in role_chars['Support'] if char not in incompatible]
        
        # Format A: 1 Main DPS + 2 Sub-DPS + 1 Support.
        for subs in combinations(sub_candidates, 2):
            for support in support_candidates:
                if support in subs:
                    continue
                team = [main] + list(subs) + [support]
                if len(set(team)) != 4:
                    continue
                if not is_unique_team(team):
                    continue
                score = calculate_team_score(team)
                teams_for_main.append((team, score))
        
        # Format B: 1 Main DPS + 1 Sub-DPS + 2 Supports.
        for sub in sub_candidates:
            for supports in combinations(support_candidates, 2):
                team = [main, sub] + list(supports)
                if len(set(team)) != 4:
                    continue
                if not is_unique_team(team):
                    continue
                score = calculate_team_score(team)
                teams_for_main.append((team, score))
        
        teams_for_main.sort(key=lambda x: x[1], reverse=True)
        teams_for_main = teams_for_main[:max_teams_per_dps]
        main_dps_usage[main] += len(teams_for_main)
        collected_teams.extend(teams_for_main)
    
    collected_teams.sort(key=lambda x: x[1], reverse=True)
    final_teams = [team for team, score in collected_teams][:num_teams]
    if not final_teams and len(expanded_characters) >= 4:
        unique_characters = set(expanded_characters)
        fallback_team = tier_sort(unique_characters, character_data)[:4]
        final_teams = [fallback_team]
    return final_teams





@app.post("/explain_teams_with_gemini")
async def explain_teams_endpoint(teams: dict):
    try:
        explanation = await explain_teams(teams['teams'])
        return explanation
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/generate_teams")
async def generate_teams():     
    user_characters_raw = await get_characters()
    user_characters = [normalise(name) for name in user_characters_raw]
    character_data = load_character_data()
    user_characters = expand_traveler_variants(user_characters, character_data)

    recommended_teams = generate_teams_optimized(user_characters, character_data,6,2)
    print(recommended_teams)
    teams_for_explanation = []

    for i, team in enumerate(recommended_teams):
        formatted_team = {
            "Team Name": f"Team {i + 1}",
            "Characters": [
                {
                    "Name": char,
                    "Role": ', '.join(character_data[char]['roles']),
                    "Element": character_data[char]['element'],
                    "Tier": character_data[char]['tier']
                }
                for char in team
            ]
        }
        teams_for_explanation.append(formatted_team)

    explanation = await explain_teams(teams_for_explanation)

    t1 = time.time() - start
    print(f"Execution Time: {t1:.2f} seconds")
    return {
        "teams": teams_for_explanation,
        "explanation": explanation,
        "status": "success"
    }


@app.post("/generate_teams_from_selection")
async def generate_teams_from_selection(request:Request):
    data = await request.json()
    user_characters = data.get('characters', [])
    print(f"test {user_characters}")     
    character_data = load_character_data()

    recommended_teams = generate_teams_optimized(user_characters, character_data,6,2)
    print(f"Recommended teams:{recommended_teams}")
    teams_for_explanation = []

    for i, team in enumerate(recommended_teams):
        formatted_team = {
            "Team Name": f"Team {i + 1}",
            "Characters": [
                {
                    "Name": char,
                    "Role": ', '.join(character_data[char]['roles']),
                    "Element": character_data[char]['element'],
                    "Tier": character_data[char]['tier']
                }
                for char in team
            ]
        }
        teams_for_explanation.append(formatted_team)

    explanation = await explain_teams(teams_for_explanation)

    t1 = time.time() - start
    print(f"Execution Time: {t1:.2f} seconds")
    return {
        "teams": teams_for_explanation,
        "explanation": explanation,
        "status": "success"
    }
