# convert_tflite.py
import numpy as np
import tensorflow as tf

WINDOW_SIZE = 4
N_FEATURES  = 4   # X, Y, Z, total

# ── Load the trained Keras model ──────────────────────────────────────────────
model = tf.keras.models.load_model("model.keras")
print("Model loaded → model.keras")

# ── Load representative data for quantization ─────────────────────────────────
# The converter needs sample data to calibrate INT8 quantization ranges
X_train = np.load("../data/transformed/X_train.npy").astype(np.float32)

def representative_dataset():
    for i in range(min(200, len(X_train))):
        sample = X_train[i].reshape(1, WINDOW_SIZE, N_FEATURES)
        yield [sample]

# ── Convert ───────────────────────────────────────────────────────────────────
converter = tf.lite.TFLiteConverter.from_keras_model(model)

converter.optimizations = [tf.lite.Optimize.DEFAULT]
converter.representative_dataset = representative_dataset

# Keep float32 input/output — easier to work with in ml_service.py
converter.inference_input_type  = tf.float32
converter.inference_output_type = tf.float32

tflite_model = converter.convert()

# ── Save ──────────────────────────────────────────────────────────────────────
with open("model.tflite", "wb") as f:
    f.write(tflite_model)

size_kb = len(tflite_model) / 1024
print(f"model.tflite saved — size: {size_kb:.1f} KB")

# ── Verify the TFLite model works before copying to Pi ────────────────────────
print("\nVerifying TFLite model...")

interpreter = tf.lite.Interpreter(model_path="model.tflite")
interpreter.allocate_tensors()

input_details  = interpreter.get_input_details()
output_details = interpreter.get_output_details()

print(f"Input shape  : {input_details[0]['shape']}")   # should be [1, 4, 4]
print(f"Output shape : {output_details[0]['shape']}")  # should be [1, 1]

# Run one test inference
test_input = X_train[0].reshape(1, WINDOW_SIZE, N_FEATURES)
interpreter.set_tensor(input_details[0]['index'], test_input)
interpreter.invoke()
output = interpreter.get_tensor(output_details[0]['index'])

print(f"\nTest inference:")
print(f"Input  : {test_input.flatten()}")
print(f"Output : {output[0][0]:.4f}  ({'vibration' if output[0][0] >= 0.5 else 'normal'})")

print("\nDone — copy model.tflite and scaler.pkl to the Pi:")
print("  scp model.tflite scaler.pkl pi@<pi-ip>:~/iot-project/ml-service/")