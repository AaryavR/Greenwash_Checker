
# Educational Comment:
# This module acts as the "Switchboard Operator". 
# It takes the raw category string from the Vision AI (which might be messy like "It looks like a snack")
# and normalizes it into one of our strict allowed types: "Food", "Cosmetic", "Cleaning", or "Other".

def identify_category(vision_category_text):
    """
    Normalizes the category text.
    """
    if not vision_category_text:
        return "Other"
        
    text = vision_category_text.lower()
    
    if any(x in text for x in ["food", "drink", "snack", "beverage", "edible"]):
        return "Food"
    elif any(x in text for x in ["cosmetic", "skin", "hair", "face", "makeup", "lotion", "soap"]):
        return "Cosmetic"
    elif any(x in text for x in ["clean", "detergent", "soap", "wash"]):
        return "Cleaning"
    else:
        return "Other"