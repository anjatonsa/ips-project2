import pandas as pd
import numpy as np
import argparse
from pathlib import Path


FEATURES = ["X", "Y", "Z"]
WINDOW_SIZE = 4
STEP = 2


def load_and_label(filepath, label):
    df = pd.read_csv(filepath, comment="#")
    df = df.dropna(how="all")

    required_columns = ["_time", "X", "Y", "Z"]

    for column in required_columns:
        if column not in df.columns:
            raise ValueError(f"{filepath}: Missing required column: {column}")

    df = df[["_time", "X", "Y", "Z"]]

    for col in ["X", "Y", "Z"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    #df["total"] = np.sqrt(df["X"]**2 + df["Y"]**2 + df["Z"]**2)

    df = df.dropna(subset=FEATURES)
    df = df.sort_values("_time")
    df["label"] = label

    return df


def main():
    parser = argparse.ArgumentParser(description="Process InfluxDB CSV files and create ML windows.")

    parser.add_argument("output", help="Output directory")
    parser.add_argument("--window-size", type=int, default=WINDOW_SIZE, help="Number of samples in each window")
    parser.add_argument("--step", type=int, default=STEP, help="Step between windows")
    parser.add_argument("files", nargs="+", help="Pairs: input.csv label input2.csv label ...")

    args = parser.parse_args()

    if len(args.files) % 2 != 0:
        raise ValueError("Each input file must have a corresponding label. Example: file1.csv 0 file2.csv 1")

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    window_size = args.window_size
    step = args.step

    all_dfs = []
    for file_index in range(0, len(args.files), 2):
        filepath = args.files[file_index]
        label = int(args.files[file_index + 1])
        df = load_and_label(filepath, label)
        all_dfs.append(df)

    X_train_all, X_test_all = [], []
    y_train_all, y_test_all = [], []

    for df in all_dfs:
        label = df["label"].iloc[0]

        # Split raw rows 80/20 BEFORE windowing
        split = int(len(df) * 0.8)
        df_train = df.iloc[:split]
        df_test  = df.iloc[split:]

        # Extract windows from each split separately
        for start in range(0, len(df_train) - window_size + 1, step):
            window = df_train.iloc[start:start + window_size]
            X_train_all.append(window[FEATURES].values)
            y_train_all.append(label)

        for start in range(0, len(df_test) - window_size + 1, step):
            window = df_test.iloc[start:start + window_size]
            X_test_all.append(window[FEATURES].values)
            y_test_all.append(label)

    X_train = np.array(X_train_all, dtype=np.float32)
    X_test  = np.array(X_test_all,  dtype=np.float32)
    y_train = np.array(y_train_all, dtype=np.int64)
    y_test  = np.array(y_test_all,  dtype=np.int64)

    np.save(output_dir / "X_train.npy", X_train)
    np.save(output_dir / "X_test.npy",  X_test)
    np.save(output_dir / "y_train.npy", y_train)
    np.save(output_dir / "y_test.npy",  y_test)


if __name__ == "__main__":
    main()