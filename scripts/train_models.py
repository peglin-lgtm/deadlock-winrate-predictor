import pandas as pd
import joblib
import os

from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, roc_auc_score



pd.set_option("display.max_columns", None)

df = pd.read_csv("data/deadlock_dataset.csv")

X = df.drop(columns="target")
y = df["target"]

split_index = int(len(df) * 0.8)

X_train = X.iloc[:split_index].copy()
y_train = y.iloc[:split_index].copy()

X_test = X.iloc[split_index:].copy()
y_test = y.iloc[split_index:].copy()

print("X_train:", X_train.shape)
print("y_train:", y_train.shape)

print("X_test:", X_test.shape)
print("y_test:", y_test.shape)


trained_models = {}
results = {}

models = {

    "Logistic Regression": make_pipeline(
        StandardScaler(),
        LogisticRegression(
            C=0.001,
            penalty="l2",
            solver="saga",
            max_iter=5000,
            random_state=42
        )
    ), 

    "Random Forest": RandomForestClassifier(
        n_estimators=200,
        min_samples_split=20,
        min_samples_leaf=2,
        max_features=0.75,
        max_depth=6,
        criterion="log_loss",
        bootstrap=True,
        random_state=42,
        n_jobs=-1
    )
}

for model_name, model in models.items():
    model.fit(X_train, y_train)

    # Evaluate on the most recent 20% to preserve chronological order.
    y_pred = model.predict(X_test)

    y_probability = model.predict_proba(X_test)[:, 1]

    train_accuracy = model.score(X_train, y_train)

    test_accuracy = accuracy_score(y_test, y_pred)
    test_roc_auc = roc_auc_score(y_test, y_probability)

    trained_models[model_name] = model

    results[model_name] = {
        "train_accuracy": train_accuracy,
        "test_accuracy": test_accuracy,
        "test_roc_auc": test_roc_auc
    }

    print(f"\n{model_name}")
    print(f"Train accuracy: {train_accuracy * 100:.2f}%")
    print(f"Test accuracy:  {test_accuracy * 100:.2f}%")
    print(f"Test ROC-AUC:   {test_roc_auc:.4f}")



os.makedirs("saved_models", exist_ok=True)

joblib.dump(
    models["Logistic Regression"],
    "saved_models/deadlock_logistic_regression.joblib"
)

joblib.dump(
    models["Random Forest"],
    "saved_models/deadlock_random_forest.joblib"
)

print("Both models have been saved")
