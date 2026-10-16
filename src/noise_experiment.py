import csv
import json
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt

from qiskit import transpile
from qiskit.quantum_info import SparsePauliOp
from qiskit_aer import AerSimulator
from qiskit_aer.noise import NoiseModel, ReadoutError, depolarizing_error

from h2_solver import H2_HAMILTONIAN, build_ansatz


# ============================================================
# Q-Molecule | Four-qubit H2 noise sensitivity experiment
# ============================================================

ROOT = Path(__file__).resolve().parents[1]
PROCESSOR_DIR = ROOT / "processors"
TABLES = ROOT / "results" / "tables"
FIGURES = ROOT / "results" / "figures"

TABLES.mkdir(parents=True, exist_ok=True)
FIGURES.mkdir(parents=True, exist_ok=True)

SHOTS = 8192
REPEATS = 3
TRANSPILER_SEED = 42
SIMULATOR_SEEDS = [42, 123, 2026]

P_1Q = 0.001
P_2Q = 0.01
P_READOUT = 0.02

BASIS_GATES = ["rz", "sx", "x", "cx"]


def load_json(path):
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


# Same illustrative noise model for both architectures.
# These values are assumptions, NOT official processor values.
noise_model = NoiseModel()

noise_model.add_all_qubit_quantum_error(
    depolarizing_error(P_1Q, 1),
    ["sx", "x"],
)

noise_model.add_all_qubit_quantum_error(
    depolarizing_error(P_2Q, 2),
    ["cx"],
)

noise_model.add_all_qubit_readout_error(
    ReadoutError([
        [1 - P_READOUT, P_READOUT],
        [P_READOUT, 1 - P_READOUT],
    ])
)

simulator = AerSimulator(noise_model=noise_model)

# Load the newest optimized four-qubit ansatz parameters.
energy_path = TABLES / "h2_energy.json"
if not energy_path.exists():
    raise FileNotFoundError(
        "Missing h2_energy.json. Run python src\\h2_solver.py first."
    )

energy_data = load_json(energy_path)
parameters = energy_data["vqe_optimal_parameters"]

if len(parameters) != 12:
    raise ValueError(
        f"Expected 12 parameters for the four-qubit ansatz; got {len(parameters)}."
    )

ansatz = build_ansatz(parameters)
exact_total = float(energy_data["exact_total_energy_hartree"])
nuclear_energy = float(
    energy_data["nuclear_repulsion_energy_hartree"]
)

# Build and compile the Pauli-measurement circuits once per processor.
# All processors use the same logical ansatz, shots, seeds and noise rates.
all_rows = []
summary_rows = []

for processor_filename in ("processor_A.json", "processor_B.json"):
    processor_path = PROCESSOR_DIR / processor_filename
    processor = load_json(processor_path)

    processor_name = processor["name"]
    coupling_map = processor["coupling_map_directed"]

    print("\n" + "=" * 65)
    print(f"NOISE SENSITIVITY — {processor_name}")
    print("=" * 65)

    compiled_terms = []

    for term_index, (label, coefficient) in enumerate(
        H2_HAMILTONIAN.to_list()
    ):
        coefficient = float(np.real(coefficient))

        if all(pauli == "I" for pauli in label):
            compiled_terms.append(
                (term_index, label, coefficient, None)
            )
            continue

        measurement_circuit = ansatz.copy()

        # Qiskit Pauli labels use the rightmost character for qubit 0.
        for qubit, pauli in enumerate(reversed(label)):
            if pauli == "X":
                measurement_circuit.h(qubit)
            elif pauli == "Y":
                measurement_circuit.sdg(qubit)
                measurement_circuit.h(qubit)

        measurement_circuit.measure_all()

        compiled = transpile(
            measurement_circuit,
            basis_gates=processor.get("basis_gates", BASIS_GATES),
            coupling_map=coupling_map,
            initial_layout=list(range(4)),
            optimization_level=0,
            routing_method="sabre",
            seed_transpiler=TRANSPILER_SEED,
        )

        compiled_terms.append(
            (term_index, label, coefficient, compiled)
        )

    processor_run_energies = []

    for repeat, simulator_seed in enumerate(SIMULATOR_SEEDS, start=1):
        electronic_energy = 0.0
        variance_estimate = 0.0

        for term_index, label, coefficient, compiled in compiled_terms:
            if compiled is None:
                # Identity terms contribute their coefficient exactly.
                electronic_energy += coefficient
                continue

            result = simulator.run(
                compiled,
                shots=SHOTS,
                seed_simulator=simulator_seed + term_index,
            ).result()

            counts = result.get_counts()
            expectation = 0.0

            for bitstring, count in counts.items():
                bits = bitstring.replace(" ", "")

                parity = sum(
                    int(bits[-1 - qubit])
                    for qubit, pauli in enumerate(reversed(label))
                    if pauli != "I"
                ) % 2

                expectation += ((-1) ** parity) * count / SHOTS

            electronic_energy += coefficient * expectation

            # Approximate shot-statistics variance for this Pauli group.
            term_variance = max(0.0, 1.0 - expectation**2) / SHOTS
            variance_estimate += coefficient**2 * term_variance

        total_energy = electronic_energy + nuclear_energy
        absolute_error = abs(total_energy - exact_total)
        shot_standard_error = float(np.sqrt(variance_estimate))

        processor_run_energies.append(total_energy)

        row = {
            "processor": processor_name,
            "repeat": repeat,
            "simulator_seed": simulator_seed,
            "shots_per_pauli_term": SHOTS,
            "single_qubit_depolarizing_probability": P_1Q,
            "two_qubit_depolarizing_probability": P_2Q,
            "readout_error_probability": P_READOUT,
            "estimated_electronic_energy_hartree": electronic_energy,
            "estimated_total_energy_hartree": total_energy,
            "absolute_error_from_exact_hartree": absolute_error,
            "estimated_shot_standard_error_hartree": shot_standard_error,
            "noise_parameters_official": False,
            "hardware_execution": False,
        }

        all_rows.append(row)

        print(
            f"Run {repeat} | seed={simulator_seed} | "
            f"total energy={total_energy:.10f} Ha | "
            f"absolute error={absolute_error:.6f} Ha | "
            f"shot SE≈{shot_standard_error:.6f} Ha"
        )

    energies = np.asarray(processor_run_energies, dtype=float)

    summary = {
        "processor": processor_name,
        "experiment": "common_illustrative_noise_sensitivity_test",
        "repeat_count": REPEATS,
        "shots_per_pauli_term": SHOTS,
        "simulator_seeds": SIMULATOR_SEEDS,
        "mean_total_energy_hartree": float(np.mean(energies)),
        "sample_std_total_energy_hartree": float(
            np.std(energies, ddof=1)
        ),
        "mean_absolute_error_from_exact_hartree": float(
            np.mean(np.abs(energies - exact_total))
        ),
        "exact_reference_total_energy_hartree": exact_total,
        "single_qubit_depolarizing_probability": P_1Q,
        "two_qubit_depolarizing_probability": P_2Q,
        "readout_error_probability": P_READOUT,
        "noise_parameters_official": False,
        "hardware_execution": False,
    }

    summary_rows.append(summary)

    print(f"\n{processor_name} summary:")
    print(
        f"Mean total energy: "
        f"{summary['mean_total_energy_hartree']:.10f} Ha"
    )
    print(
        f"Sample standard deviation: "
        f"{summary['sample_std_total_energy_hartree']:.6f} Ha"
    )
    print(
        f"Mean absolute error: "
        f"{summary['mean_absolute_error_from_exact_hartree']:.6f} Ha"
    )


# Save all individual runs.
csv_path = TABLES / "noise_sensitivity.csv"

with csv_path.open("w", newline="", encoding="utf-8") as file:
    writer = csv.DictWriter(file, fieldnames=list(all_rows[0].keys()))
    writer.writeheader()
    writer.writerows(all_rows)

json_path = TABLES / "noise_sensitivity.json"

json_path.write_text(
    json.dumps(
        {
            "description": (
                "Four-qubit H2 noise-sensitivity experiment using a "
                "common illustrative noise model on two participant-designed "
                "connectivity graphs."
            ),
            "exact_reference_total_energy_hartree": exact_total,
            "common_noise_model": {
                "single_qubit_depolarizing_probability": P_1Q,
                "two_qubit_depolarizing_probability": P_2Q,
                "readout_error_probability": P_READOUT,
                "official_processor_noise": False,
            },
            "repeat_count": REPEATS,
            "shots_per_pauli_term": SHOTS,
            "individual_runs": all_rows,
            "results": summary_rows,
        },
        indent=2,
    ),
    encoding="utf-8",
)

# Plot mean energies with sample standard-deviation error bars.
names = [row["processor"] for row in summary_rows]
means = [
    row["mean_total_energy_hartree"]
    for row in summary_rows
]
stds = [
    row["sample_std_total_energy_hartree"]
    for row in summary_rows
]

fig, ax = plt.subplots(figsize=(8, 5))
ax.bar(names, means, yerr=stds, capsize=6)
ax.axhline(
    exact_total,
    linestyle="--",
    linewidth=2,
    label="Exact reference",
)
ax.set_ylabel("Total energy (Hartree)")
ax.set_title("H₂ Energy Under a Common Illustrative Noise Model")
ax.legend()
ax.grid(axis="y", alpha=0.25)
fig.tight_layout()

plot_path = FIGURES / "noise_sensitivity.png"
fig.savefig(plot_path, dpi=200, bbox_inches="tight")
plt.close(fig)

print("\n" + "=" * 65)
print("NOISE SENSITIVITY EXPERIMENT COMPLETED")
print("=" * 65)
print(f"Individual runs CSV: {csv_path}")
print(f"Run and summary JSON: {json_path}")
print(f"Comparison graph: {plot_path}")
print("All noise parameters are illustrative, not official.")
print("Results are simulation estimates, not physical hardware measurements.")