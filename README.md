# CV_CandidatFR

python generate_all_profiles.py                          # tous les candidats avec un slug
python generate_all_profiles.py --only jean-luc-melenchon # un seul candidat
python generate_all_profiles.py --max-pages 5             # recherche plus légère/rapide
python generate_all_profiles.py --skip-existing           # ne relance pas ce qui est déjà généré


'python candidate_profile.py jean-luc-melenchon --chambre deputes --out jean-luc-melenchon.json'

python render_profile.py elisabeth-borne.json --out elisabeth-borne.html

pytest -q


python -m http.server 8000