import json
from pathlib import Path

import numpy as np
from scipy.optimize import minimize
from qiskit import QuantumCircuit
from qiskit.quantum_info import SparsePauliOp, Statevector

# ============================================================
# Q-Molecule | C1: H2 Ground-State Energy
# Full four-qubit Jordan-Wigner Hamiltonian
# ============================================================

BOND_DISTANCE_ANGSTROM = 0.735
BASIS_SET = "STO-3G"
NUCLEAR_REPULSION_HARTREE = 0.7199689944489797
RANDOM_SEEDS = [42, 1, 2]
CHEMICAL_ACCURACY_HARTREE = 0.0016

# Precomputed H2/STO-3G four-qubit Jordan-Wigner Hamiltonian.
# Coefficients are rounded to 8 decimal places from the
# Qiskit Nature mapping tutorial. No local PySCF integral
# generation is performed in this Windows-compatible workflow.
H2_HAMILTONIAN = SparsePauliOp.from_list([
    ("IIII", -0.81054798),
    ("IIIZ",  0.17218393),
    ("IIZI", -0.22575349),
    ("IZII",  0.17218393),
    ("ZIII", -0.22575349),
    ("IIZZ",  0.12091263),
    ("IZIZ",  0.16892754),
    ("ZIIZ",  0.16614543),
    ("YYYY",  0.04523280),
    ("XXYY",  0.04523280),
    ("YYXX",  0.04523280),
    ("XXXX",  0.04523280),
    ("IZZI",  0.16614543),
    ("ZIZI",  0.17464343),
    ("ZZII",  0.12091263),
])


def build_ansatz(parameters):
    """Four-qubit hardware-efficient ring ansatz with 12 parameters."""
    if len(parameters) != 12:
        raise ValueError(
            f"Expected 12 parameters, received {len(parameters)}."
        )

    circuit = QuantumCircuit(4)

    # Initial single-qubit rotations.
    for qubit in range(4):
        circuit.ry(float(parameters[qubit]), qubit)

    for qubit in range(4):
        circuit.rz(float(parameters[4 + qubit]), qubit)

    # Ring entanglement. The 3--0 interaction is direct on
    # our chosen Processor A graph but requires routing on B.
    for control, target in [
        (0, 1),
        (1, 2),
        (2, 3),
        (3, 0),
    ]:
        circuit.cx(control, target)

    # Final variational rotations.
    for qubit in range(4):
        circuit.ry(float(parameters[8 + qubit]), qubit)

    return circuit


def energy_electronic(parameters):
    """Return the electronic energy expectation in Hartree."""
    state = Statevector.from_instruction(build_ansatz(parameters))
    value = state.expectation_value(H2_HAMILTONIAN)
    return float(np.real(value))


def main():
    # Exact reference for the stored, rounded-coefficient Hamiltonian.
    exact_electronic = float(
        np.linalg.eigvalsh(H2_HAMILTONIAN.to_matrix())[0]
    )
    exact_total = exact_electronic + NUCLEAR_REPULSION_HARTREE

    print("=" * 62)
    print("Q-MOLECULE: H2 GROUND-STATE ENERGY")
    print("=" * 62)
    print(f"Bond distance: {BOND_DISTANCE_ANGSTROM} Angstrom")
    print(f"Basis label: {BASIS_SET}")
    print("Mapping: Jordan-Wigner")
    print(f"Logical qubits: {H2_HAMILTONIAN.num_qubits}")
    print(f"Hamiltonian Pauli terms: {len(H2_HAMILTONIAN)}")
    print(f"Exact electronic energy: {exact_electronic:.12f} Ha")
    print(f"Nuclear repulsion: {NUCLEAR_REPULSION_HARTREE:.12f} Ha")
    print(f"Exact total energy: {exact_total:.12f} Ha")

    # Use deterministic, independent starting points.
    # Retain the best result across all attempts.
    best_result = None
    total_evaluations = 0

    for seed in RANDOM_SEEDS:
        rng = np.random.default_rng(seed)
        initial = rng.uniform(-0.5, 0.5, size=12)

        result = minimize(
            energy_electronic,
            initial,
            method="L-BFGS-B",
            options={
                "maxiter": 1000,
                "ftol": 1e-12,
            },
        )

        total_evaluations += int(result.nfev)

        print(
            f"Seed {seed}: energy={result.fun:.12f} Ha, "
            f"success={result.success}, evaluations={result.nfev}"
        )

        if best_result is None or result.fun < best_result.fun:
            best_result = result

    optimal_parameters = [
        float(value) for value in best_result.x
    ]

    vqe_electronic = float(best_result.fun)
    vqe_total = vqe_electronic + NUCLEAR_REPULSION_HARTREE
    absolute_error = abs(vqe_total - exact_total)

    print("\nBEST VQE RESULT")
    print(f"Electronic energy: {vqe_electronic:.12f} Ha")
    print(f"Total energy: {vqe_total:.12f} Ha")
    print(f"Absolute energy error: {absolute_error:.6e} Ha")
    print(f"Best-run optimizer success: {best_result.success}")
    print(f"Total evaluations across starts: {total_evaluations}")
    print(f"Chemical accuracy achieved: {absolute_error <= CHEMICAL_ACCURACY_HARTREE}")

    project_root = Path(__file__).resolve().parents[1]
    output_dir = project_root / "results" / "tables"
    output_dir.mkdir(parents=True, exist_ok=True)

    output = {
        "problem_code": "C1",
        "problem_name": "Molecular Ground-State Energy (H2)",
        "molecule": "H2",
        "bond_distance_angstrom": BOND_DISTANCE_ANGSTROM,
        "basis_set_label": BASIS_SET,
        "mapping": "Jordan-Wigner",
        "hamiltonian_qubits": 4,
        "hamiltonian_pauli_terms": 15,
        "hamiltonian_provenance": (
            "Precomputed coefficients transcribed from the "
            "Qiskit Nature mapping tutorial, rounded to 8 decimal places."
        ),
        "integrals_generated_locally": False,
        "nuclear_repulsion_energy_hartree": NUCLEAR_REPULSION_HARTREE,
        "exact_electronic_energy_hartree": exact_electronic,
        "exact_total_energy_hartree": exact_total,
        "vqe_electronic_energy_hartree": vqe_electronic,
        "vqe_total_energy_hartree": vqe_total,
        "absolute_total_energy_error_hartree": absolute_error,
        "optimizer": "L-BFGS-B",
        "optimizer_success": bool(best_result.success),
        "optimizer_message": str(best_result.message),
        "random_seeds": RANDOM_SEEDS,
        "total_function_evaluations": total_evaluations,
        "ansatz": "Four-qubit hardware-efficient ring ansatz",
        "vqe_optimal_parameters": optimal_parameters,
        "chemical_accuracy_threshold_hartree": CHEMICAL_ACCURACY_HARTREE,
        "within_chemical_accuracy": bool(
            absolute_error <= CHEMICAL_ACCURACY_HARTREE
        ),
    }

    out_path = output_dir / "h2_energy.json"
    out_path.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(f"\nSaved: {out_path}")


if __name__ == "__main__":
    main()
