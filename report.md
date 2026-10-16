# Q-Molecule — Phase 1 C1: Molecular Ground-State Energy (H₂)

## 1. Project Summary

This project investigates the H₂ molecular ground-state energy using a four-qubit precomputed Hamiltonian and a hardware-efficient variational quantum eigensolver (VQE). It compares circuit compilation for two participant-designed processor connectivity graphs and performs a separate noise-sensitivity experiment.

All measurements reported here come from classical simulation and circuit compilation. No physical quantum hardware was accessed.

## 2. Problem and Method

| Parameter | Value |
|---|---|
| Challenge problem | C1 — Molecular Ground-State Energy (H₂) |
| Bond distance | 0.735 Å |
| Basis-set label | STO-3G |
| Mapping | Jordan–Wigner |
| Hamiltonian qubits | 4 |
| Pauli terms | 15 |
| Variational ansatz | Four-qubit hardware-efficient ring |
| Optimizer | L-BFGS-B |
| Random seeds | 42, 1, 2 |

The Hamiltonian coefficients were transcribed from a Qiskit Nature mapping tutorial and rounded to eight decimal places. Molecular integrals were not generated locally with PySCF.

The exact reference energy was obtained by diagonalizing the same stored Hamiltonian. It is therefore a reference for the implemented operator, not an independent validation of a newly generated molecular-integral workflow.

## 3. H₂ Energy Results

| Metric | Result |
|---|---:|
| Exact electronic energy | −1.857275009288 Ha |
| Nuclear repulsion energy | 0.719968994449 Ha |
| Exact total energy of stored Hamiltonian | −1.137306014839 Ha |
| VQE electronic energy | −1.857275009275 Ha |
| VQE total energy | −1.137306014826 Ha |
| Absolute total-energy error | 1.37 × 10⁻¹¹ Ha |
| Optimizer convergence | Successful |
| Function evaluations across starts | 897 |

The VQE result closely matches the exact eigenvalue of the implemented Hamiltonian and is within the specified 0.0016 Ha chemical-accuracy threshold for this reference. This comparison does not establish independent chemical accuracy against a separately generated molecular reference.

## 4. Processor Architectures

The processor graphs below are participant-designed configurations, permitted as custom designs in the provided organizer discussion. They are not claimed to be official hardware edge lists.

### Processor A

- Physical qubits: 5
- Undirected edges: (0,1), (1,2), (2,3), (3,0), (2,4)
- Basis gates: `rz`, `sx`, `x`, `cx`
- Noise probabilities in the configuration: illustrative assumptions, not official specifications

### Processor B

- Physical qubits: 9
- Undirected edges: (0,1), (1,2), (2,3), (3,4), (4,5), (5,6), (6,7), (7,8), (1,8), (3,7)
- Basis gates: `rz`, `sx`, `x`, `cx`
- No official Processor B noise parameters were supplied in the available organizer discussion

## 5. Connectivity-Constrained Compilation

Compilation used Qiskit's transpiler, SABRE routing, optimization level 0, initial layout `[0, 1, 2, 3]`, and seed 42.

### Main H₂ ansatz

| Metric | Processor A | Processor B |
|---|---:|---:|
| Available physical qubits | 5 | 9 |
| Logical qubits | 4 | 4 |
| Compiled circuit width | 5 | 9 |
| Active physical qubits | 4 | 4 |
| Logical depth | 7 | 7 |
| Routed depth before SWAP decomposition | 15 | 21 |
| Final transpiled depth | 15 | 23 |
| Logical gate count | 16 | 16 |
| Final transpiled gate count | 48 | 54 |
| Baseline CX count | 4 | 4 |
| Final CX count | 4 | 10 |
| CX overhead | 0 | 6 |
| Routing SWAPs before decomposition | 0 | 2 |

For the selected ansatz and initial layout, Processor A's graph includes the direct connection (3,0), while Processor B's graph does not. This is consistent with the observed difference in routing overhead for this circuit and transpiler configuration.

### Supplementary four-qubit routing probe

| Metric | Processor A | Processor B |
|---|---:|---:|
| Logical depth | 7 | 7 |
| Routed depth before SWAP decomposition | 11 | 15 |
| Final transpiled depth | 17 | 25 |
| Logical gate count | 16 | 16 |
| Final transpiled gate count | 33 | 42 |
| Baseline CX count | 8 | 8 |
| Final CX count | 17 | 26 |
| CX overhead | 9 | 18 |
| Routing SWAPs before decomposition | 3 | 6 |

The routing probe is supplementary and is not used to calculate the H2 energy. Under the current circuit construction and transpiler settings, Processor B has greater final depth and CX overhead for this probe. This is specific to the tested circuit and configuration, not a universal ranking of processor quality.

## 6. Illustrative Noise Experiment

The noise experiment used the same illustrative model for both processor configurations:

| Parameter | Value |
|---|---:|
| Single-qubit depolarizing probability | 0.001 |
| Two-qubit depolarizing probability | 0.01 |
| Readout-error probability | 0.02 |
| Shots per Pauli term | 8192 |
| Independent simulator seeds | 42, 123, 2026 |

These probabilities are assumptions, not official processor specifications. The experiment is a controlled simulator study and not a prediction of actual device performance.

| Metric | Processor A | Processor B |
|---|---:|---:|
| Mean estimated total energy | −1.045838 Ha | −1.016180 Ha |
| Mean absolute error from reference | 0.091468 Ha | 0.121126 Ha |
| Sample standard deviation across three runs | 0.002398 Ha | 0.002278 Ha |

Only three independent runs were used, so these standard deviations are limited estimates of run-to-run variability. The two configurations' noise results should be interpreted under the common illustrative model, not as a comparison of official processor noise characteristics.

## 7. Limitations

1. The Hamiltonian is precomputed and rounded. Molecular integrals were not generated locally.
2. The ansatz is hardware-efficient and is not UCCSD.
3. The exact reference is calculated from the same stored Hamiltonian.
4. The two processor connectivity graphs are participant-designed configurations.
5. The noise probabilities are illustrative and are not official device specifications.
6. Compilation and noise results are simulator-based; no physical hardware experiment was performed.
7. Results depend on the selected circuits, initial layout, transpiler settings, connectivity and noise assumptions.

## 8. Reproducibility

Use Python 3.12 and install dependencies from `requirements.txt` in a clean environment. From the repository root on Windows, run:

```powershell
python -m pip install -r requirements.txt
python processors/processor_A.py
python processors/processor_B.py
python src/h2_solver.py
python src/benchmark_processors.py
python src/noise_experiment.py
```

Open `main.ipynb` in VS Code using the project's Python environment and run its cells from top to bottom. The scripts generate the result tables and figures under `results/tables/` and `results/figures/`.

## 9. AI Assistance Disclosure

AI assistance was used to help draft, debug and document parts of this project. The reported methods, assumptions and limitations are disclosed above; the final submission should be reviewed by the project author.

## 10. Conclusion

The VQE optimizer closely reproduces the exact ground-state energy of the stored four-qubit H₂ Hamiltonian. Compilation experiments show that the selected Processor A and Processor B connectivity graphs produce different routing overhead for the tested circuits. The separate noise experiment illustrates the sensitivity of estimated energy to an assumed noise model.

These findings apply to the particular implemented Hamiltonian, circuits, processor graphs and simulation settings. They should not be interpreted as independently validated molecular-integral results or physical-hardware performance claims.