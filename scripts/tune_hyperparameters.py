import pandas as pd
from pathlib import Path

from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GridSearchCV, RandomizedSearchCV, TimeSeriesSplit
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
pd.set_option("display.max_columns", None)

df = pd.read_csv(DATA_DIR / "deadlock_dataset.csv")

print("DataFrame size:")
print(df.shape)

print("\nFirst rows:")
print(df.head())

print("\nColumn information:")
df.info()

print("\nMissing values:")
print(df.isna().sum())

print("\nDescriptive statistics:")
print(df.describe().T)

print("\nTarget distribution:")
print(df["target"].value_counts())

print("\nTarget distribution in percentages:")
print(df["target"].value_counts(normalize=True) * 100)

X = df.drop(columns="target")
y = df["target"]

split_index = int(len(df) * 0.8)

X_train = X.iloc[:split_index].copy()
y_train = y.iloc[:split_index].copy()

logistic_model = make_pipeline(
    StandardScaler(),
    LogisticRegression(
        solver="saga",
        max_iter=5000,
        random_state=42
    )
)

param_grid = {
    "logisticregression__C": [
        0.001,
        0.01,
        0.1,
        1,
        10,
        100
    ],
    "logisticregression__l1_ratio": [
        0,
        0.25,
        0.5,
        0.75,
        1
    ]
}

cv = TimeSeriesSplit(n_splits=5)

grid_search = GridSearchCV(
    estimator=logistic_model,
    param_grid=param_grid,
    cv=cv,
    scoring={
        "accuracy": "accuracy",
        "roc_auc": "roc_auc"
    },
    refit="accuracy",
    n_jobs=-1,
    return_train_score=True
)

grid_search.fit(X_train, y_train)

best_index = grid_search.best_index_

train_accuracy = grid_search.cv_results_[
    "mean_train_accuracy"
][best_index]

validation_accuracy = grid_search.cv_results_[
    "mean_test_accuracy"
][best_index]

print("Train accuracy:", train_accuracy)
print("Validation accuracy:", validation_accuracy)
print("Difference:", train_accuracy - validation_accuracy)

print("Best parameters:")
print(grid_search.best_params_)

print("Best mean accuracy:")
print(grid_search.best_score_)

rf_model = RandomForestClassifier(
    random_state=67,
    n_jobs=1
)

param_distributions = {
    "n_estimators": [100, 200, 300, 500, 700],
    "max_depth": [
        None,
        4,
        6,
        8,
        10,
        15,
        20
    ],
    "min_samples_split": [
        2,
        5,
        10,
        20
    ],
    "min_samples_leaf": [
        1,
        2,
        4,
        8,
        12
    ],
    "max_features": [
        "sqrt",
        "log2",
        0.5,
        0.75,
        None
    ],
    "bootstrap": [
        True,
        False
    ],
    "criterion": [
        "gini",
        "entropy",
        "log_loss"
    ]
}

rf_search = RandomizedSearchCV(
    estimator=rf_model,
    param_distributions=param_distributions,
    n_iter=100,
    scoring={
        "accuracy": "accuracy",
        "roc_auc": "roc_auc"
    },
    refit="accuracy",
    cv=cv,
    random_state=67,
    n_jobs=-1,
    verbose=1,
    return_train_score=True
)

rf_search.fit(X_train, y_train)

print("Best parameters:")
print(rf_search.best_params_)

print("\nBest mean cross-validation accuracy:")
print(rf_search.best_score_)

print(f"\nBest accuracy: {rf_search.best_score_ * 100:.2f}%")
