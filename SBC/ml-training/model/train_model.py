# train_model.py
import numpy as np
import pickle
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.preprocessing import StandardScaler
import tensorflow as tf
import json
# ── Config ────────────────────────────────────────────────────────────────────
WINDOW_SIZE = 4
N_FEATURES  = 3       # X, Y, Z, total
EPOCHS      = 30
BATCH_SIZE  = 16

# ── Load ──────────────────────────────────────────────────────────────────────
X_train = np.load("../data/transformed/X_train.npy")
X_test  = np.load("../data/transformed/X_test.npy")
y_train = np.load("../data/transformed/y_train.npy")
y_test  = np.load("../data/transformed/y_test.npy")

print(f"X_train : {X_train.shape}  |  y_train : {y_train.shape}")
print(f"X_test  : {X_test.shape}   |  y_test  : {y_test.shape}")
print(f"Train — Normal (0): {(y_train==0).sum()}  |  Anomaly (1): {(y_train==1).sum()}")
print(f"Test  — Normal (0): {(y_test==0).sum()}   |  Anomaly (1): {(y_test==1).sum()}")

# ── Scale ─────────────────────────────────────────────────────────────────────
# Fit scaler ONLY on train data, then apply to both — never fit on test data
N_train = X_train.shape[0]
N_test  = X_test.shape[0]

scaler = StandardScaler()
X_train = scaler.fit_transform(X_train.reshape(-1, N_FEATURES)).reshape(N_train, WINDOW_SIZE, N_FEATURES)
X_test  = scaler.transform(X_test.reshape(-1, N_FEATURES)).reshape(N_test,  WINDOW_SIZE, N_FEATURES)

scaler_params = {
    "mean": scaler.mean_.tolist(),
    "scale": scaler.scale_.tolist(),
    "n_features": int(scaler.n_features_in_)
}

with open("scaler.json", "w") as f:
    json.dump(scaler_params, f)

print("Scaler saved → scaler.json")

# ── Model ─────────────────────────────────────────────────────────────────────
model = tf.keras.Sequential([
    tf.keras.layers.Input(shape=(WINDOW_SIZE, N_FEATURES)),
    tf.keras.layers.Conv1D(32, kernel_size=3, activation="relu", padding="same"),
    tf.keras.layers.Conv1D(16, kernel_size=3, activation="relu", padding="same"),
    tf.keras.layers.GlobalAveragePooling1D(),
    tf.keras.layers.Dense(16, activation="relu"),
    tf.keras.layers.Dropout(0.3),
    tf.keras.layers.Dense(1, activation="sigmoid"),
])

model.summary()

model.compile(
    optimizer="adam",
    loss="binary_crossentropy",
    metrics=["accuracy"]
)

# ── Train ─────────────────────────────────────────────────────────────────────
early_stop = tf.keras.callbacks.EarlyStopping(
    monitor="val_loss",
    patience=5,
    restore_best_weights=True
)

model.fit(
    X_train, y_train,
    epochs=EPOCHS,
    batch_size=BATCH_SIZE,
    validation_split=0.1,
    callbacks=[early_stop]
)

# ── Evaluate ──────────────────────────────────────────────────────────────────
print("\n── Test set evaluation ──────────────────────────")
loss, acc = model.evaluate(X_test, y_test, verbose=0)
print(f"Loss    : {loss:.4f}")
print(f"Accuracy: {acc:.4f}")

y_pred = (model.predict(X_test) >= 0.5).astype(int).flatten()

print("\n── Classification report ────────────────────────")
print(classification_report(y_test, y_pred, target_names=["normal", "vibration"]))

print("── Confusion matrix ─────────────────────────────")
cm = confusion_matrix(y_test, y_pred)
print(f"                 Predicted")
print(f"                 normal  vibration")
print(f"Actual normal  [{cm[0][0]:^6} {cm[0][1]:^9}]")
print(f"Actual vibrat  [{cm[1][0]:^6} {cm[1][1]:^9}]")

# ── Save ──────────────────────────────────────────────────────────────────────
model.save("model.keras")
print("\nModel saved  → model.keras")
print("Next step    → run convert_tflite.py")