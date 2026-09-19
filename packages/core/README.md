# tonedown (core engine)

Grades any text on a 0 to 4 scale from safe to dangerous, tags categories, and turns probabilities into
actions through a policy. See the repository README for the full picture.

```python
from tonedown import Guard

guard = Guard()  # Jev backend if TYPESAFE_API_KEY is set, lexicon-only otherwise
for v in guard.grade(["这集节奏太好了", "OP is a brainless idiot"]):
    print(v.level_argmax, v.action, v.top_category, v.lang)
```
