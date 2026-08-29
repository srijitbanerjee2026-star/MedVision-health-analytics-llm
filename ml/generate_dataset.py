import numpy as np
import pandas as pd

# Reproducibility
np.random.seed(42)

# Number of synthetic patients
N = 5000

# ---------------------------------------------------------
# 1. Generate synthetic patient measurements
# ---------------------------------------------------------

age = np.random.randint(18, 91, N)

spo2 = np.random.normal(94, 5, N)
heart_rate = np.random.normal(95, 20, N)
respiratory_rate = np.random.normal(21, 6, N)
temperature = np.random.normal(37.5, 1.0, N)

# Keep values within sensible ranges for our demo
spo2 = np.clip(spo2, 75, 100)
heart_rate = np.clip(heart_rate, 50, 160)
respiratory_rate = np.clip(respiratory_rate, 10, 45)
temperature = np.clip(temperature, 35.0, 41.0)


# ---------------------------------------------------------
# 2. Create a synthetic severity score
# ---------------------------------------------------------

score = np.zeros(N)


# SpO2 contribution
score += np.where(spo2 < 90, 3, 0)
score += np.where((spo2 >= 90) & (spo2 < 94), 2, 0)
score += np.where(spo2 >= 94, 0, 0)


# Heart rate contribution
score += np.where(heart_rate > 120, 2, 0)
score += np.where((heart_rate > 100) & (heart_rate <= 120), 1, 0)


# Respiratory rate contribution
score += np.where(respiratory_rate > 30, 2, 0)
score += np.where((respiratory_rate > 22) & (respiratory_rate <= 30), 1, 0)


# Temperature contribution
score += np.where(temperature > 39, 2, 0)
score += np.where((temperature > 38) & (temperature <= 39), 1, 0)


# Age contribution
score += np.where(age >= 75, 1, 0)


# ---------------------------------------------------------
# 3. Convert score into severity classes 1–5
# ---------------------------------------------------------

severity = np.select(
    [score <= 1, score == 2, score == 3, score == 4, score >= 5], [1, 2, 3, 4, 5]
)


# ---------------------------------------------------------
# 4. Create DataFrame
# ---------------------------------------------------------

df = pd.DataFrame(
    {
        "spo2": np.round(spo2, 1),
        "heart_rate": np.round(heart_rate).astype(int),
        "respiratory_rate": np.round(respiratory_rate).astype(int),
        "temperature": np.round(temperature, 1),
        "age": age,
        "severity": severity,
    }
)


# ---------------------------------------------------------
# 5. Shuffle dataset
# ---------------------------------------------------------

df = df.sample(frac=1, random_state=42).reset_index(drop=True)


# ---------------------------------------------------------
# 6. Save dataset
# ---------------------------------------------------------

df.to_csv("ml/training_dataset.csv", index=False)

print("Dataset created successfully!")
print()
print(df.head(10))
print()
print("Dataset shape:", df.shape)
print()
print("Severity distribution:")
print(df["severity"].value_counts().sort_index())
