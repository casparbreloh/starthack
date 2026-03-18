"""
Static biological rules for the five mission crops.

Parameters
----------
growth_days         : sols to full maturity
kcal_per_100g       : caloric density
protein_per_100g_g  : protein per 100 g fresh weight
yield_kg_per_m2     : fresh-mass yield at full health/maturity
water_L_per_m2_per_sol : irrigation demand
n_demand_ppm        : optimal nitrogen in nutrient solution
temp_response       : [t_min, t_opt_low, t_opt_high, t_max] °C
par_saturation      : PAR (µmol/m²/s) at which photosynthesis saturates
provides_micronutrients : True if crop covers Vit K/A requirements
"""

from src.enums import CropType

CROP_CATALOG: dict[CropType, dict] = {
    CropType.LETTUCE: {
        "name": "Lettuce",
        "growth_days": 35,
        "kcal_per_100g": 15,
        "protein_per_100g_g": 1.3,
        "yield_kg_per_m2": 4.0,
        "water_L_per_m2_per_sol": 2.5,
        "n_demand_ppm": 150.0,
        "temp_response": [5.0, 14.0, 22.0, 30.0],
        "par_saturation": 200.0,
        "provides_micronutrients": True,
        "notes": "Vital micronutrient source (Vit K, A). High water need. Fast cycle.",
    },
    CropType.POTATO: {
        "name": "Potato",
        "growth_days": 90,
        "kcal_per_100g": 77,
        "protein_per_100g_g": 2.0,
        "yield_kg_per_m2": 15.0,
        "water_L_per_m2_per_sol": 2.0,
        "n_demand_ppm": 120.0,
        "temp_response": [5.0, 15.0, 20.0, 30.0],
        "par_saturation": 300.0,
        "provides_micronutrients": False,
        "notes": "Carbohydrate backbone. Tolerates lower light. Best ROI on area.",
    },
    CropType.RADISH: {
        "name": "Radish",
        "growth_days": 25,
        "kcal_per_100g": 16,
        "protein_per_100g_g": 0.7,
        "yield_kg_per_m2": 2.5,
        "water_L_per_m2_per_sol": 1.5,
        "n_demand_ppm": 100.0,
        "temp_response": [4.0, 14.0, 22.0, 28.0],
        "par_saturation": 180.0,
        "provides_micronutrients": False,
        "notes": "Fastest cycle. Emergency buffer crop.",
    },
    CropType.BEANS: {
        "name": "Beans/Peas",
        "growth_days": 60,
        "kcal_per_100g": 100,
        "protein_per_100g_g": 9.0,
        "yield_kg_per_m2": 5.0,
        "water_L_per_m2_per_sol": 2.2,
        "n_demand_ppm": 80.0,          # nitrogen-fixing; lower external demand
        "temp_response": [8.0, 18.0, 25.0, 35.0],
        "par_saturation": 350.0,
        "provides_micronutrients": False,
        "notes": "Primary protein source. Nitrogen-fixing reduces fertilizer need.",
    },
    CropType.HERBS: {
        "name": "Herbs",
        "growth_days": 15,
        "kcal_per_100g": 40,
        "protein_per_100g_g": 3.0,
        "yield_kg_per_m2": 0.5,
        "water_L_per_m2_per_sol": 0.8,
        "n_demand_ppm": 80.0,
        "temp_response": [8.0, 16.0, 24.0, 32.0],
        "par_saturation": 150.0,
        "provides_micronutrients": False,
        "notes": "Low caloric yield. Psychological and flavour benefit for crew.",
    },
}
