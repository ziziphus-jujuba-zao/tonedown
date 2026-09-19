# Public datasets

Raw files are never committed (`eval/datasets/raw/` is git-ignored). Download them yourself, check
each license, then convert to the golden JSONL shape with `convert.py`.

| Dataset | Languages | Where | Notes |
|---|---|---|---|
| Jigsaw Multilingual Toxic Comment Classification | en, es, fr, it, pt, ru, tr | Kaggle competition data | binary toxic label; map toxic=1 to level 2 |
| COLD (Chinese Offensive Language Dataset) | zh | github.com/thu-coai/COLDataset | offensive / non-offensive, with topic labels |
| ToxiCN | zh | github.com/DUT-lab/ToxiCN | fine-grained toxicity, hate and insult types |
| HateXplain | en | huggingface.co/datasets/hatexplain | hate / offensive / normal with rationales |
| KOLD | ko | github.com/boychaboy/KOLD | offensive language with targets |
| PolygloToxicityPrompts | 17 languages | huggingface.co/datasets/ToxicityPrompts/PolygloToxicityPrompts | toxicity scores from Perspective |

Binary labels only tell you whether level 2 or more is right; they cannot grade the 0-4 scale. Use them
for the F1(level≥2) column and keep the hand-labelled golden set for exact levels.
