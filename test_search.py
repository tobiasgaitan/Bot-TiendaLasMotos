import difflib

def test_search():
    query_tokens = ["raider"]
    item_tokens = ["victory", "bomber", "125", "tk", "trabajo", "mecanica"]
    clean_query = " ".join(query_tokens)
    name_clean = "victory bomber 125 tk"
    item_search_text = "victory bomber 125 tk trabajo mecanica"
    
    score = 0
    if clean_query in name_clean:
        score += 100
    elif clean_query in item_search_text:
        score += 85
        
    if len(query_tokens) > 0:
        matches = 0
        for t in query_tokens:
            if t in item_tokens:
                matches += 1
            else:
                fuzzy_hit = False
                for target_token in set(item_tokens):
                    r = difflib.SequenceMatcher(None, t, target_token).ratio()
                    if r > 0.8:
                        print(f"Fuzzy hit! {t} vs {target_token} (ratio {r})")
                        fuzzy_hit = True
                        break
                if fuzzy_hit:
                    matches += 0.8
        
        if matches >= len(query_tokens):
            score += 90 
        elif matches > 0:
            score += (matches / len(query_tokens)) * 70

    ratio = difflib.SequenceMatcher(None, clean_query, name_clean).ratio()
    if ratio > 0.6:
        score += ratio * 60
        
    print(f"Final Score: {score}")

test_search()
