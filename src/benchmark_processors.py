
"""Processor A/B compilation benchmark for Q-Molecule Phase 1 C1.

Compiles the same four-qubit H2 ansatz against both participant-designed
connectivity graphs. Also runs a supplementary routing probe.

All measurements are classical compilation results, not hardware results.
"""

import csv
import json
import time
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from qiskit import QuantumCircuit, transpile

from h2_solver import build_ansatz


ROOT = Path(__file__).resolve().parents[1]
PROCESSOR_DIR = ROOT / "processors"
TABLES = ROOT / "results" / "tables"
FIGURES = ROOT / "results" / "figures"

TABLES.mkdir(parents=True, exist_ok=True)
FIGURES.mkdir(parents=True, exist_ok=True)

SEED = 42
OPT_LEVEL = 0


def load_json(path):
    """Load a JSON file using UTF-8."""
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def build_routing_probe():
    """Build a supplementary four-qubit routing circuit, not an H2 solver."""
    qc = QuantumCircuit(4)

    for q in range(4):
        qc.h(q)
        qc.rz(0.17 * (q + 1), q)

    interactions = [
        (0, 3),
        (0, 2),
        (1, 3),
        (1, 2),
        (0, 1),
        (2, 3),
        (0, 3),
        (1, 2),
    ]

    for control, target in interactions:
        qc.cx(control, target)

    return qc


def active_physical_qubits(circuit):
    """Count qubits used by non-barrier, non-delay instructions."""
    active = set()

    for instruction in circuit.data:
        operation = instruction.operation

        if operation.name in {"barrier", "delay"}:
            continue

        for qubit in instruction.qubits:
            active.add(circuit.find_bit(qubit).index)

    return len(active)


def get_undirected_edges(config):
    """Read undirected edges, falling back to the directed coupling map."""
    edges = config.get("coupling_edges_undirected")

    if edges:
        return [tuple(edge) for edge in edges]

    seen = set()
    undirected = []

    for a, b in config["coupling_map_directed"]:
        edge = tuple(sorted((int(a), int(b))))

        if edge not in seen:
            seen.add(edge)
            undirected.append(edge)

    return undirected


def draw_processor_graph(config, output_path):
    """Draw and save a processor connectivity graph without NetworkX."""
    num_qubits = int(config["num_qubits"])
    edges = get_undirected_edges(config)

    angles = np.linspace(0, 2 * np.pi, num_qubits, endpoint=False)
    positions = {
        node: (float(np.cos(angle)), float(np.sin(angle)))
        for node, angle in enumerate(angles)
    }

    fig, ax = plt.subplots(figsize=(7, 6))

    for a, b in edges:
        x1, y1 = positions[a]
        x2, y2 = positions[b]
        ax.plot(
            [x1, x2],
            [y1, y2],
            linewidth=2,
            color="#52718f",
            zorder=1,
        )

    xs = [positions[node][0] for node in range(num_qubits)]
    ys = [positions[node][1] for node in range(num_qubits)]

    ax.scatter(
        xs,
        ys,
        s=950,
        color="#12314d",
        edgecolors="#00cfe8",
        linewidths=2,
        zorder=2,
    )

    for node, (x, y) in positions.items():
        ax.text(
            x,
            y,
            str(node),
            ha="center",
            va="center",
            color="white",
            fontsize=11,
            fontweight="bold",
            zorder=3,
        )

    ax.set_title(
        f"{config['name']} - {num_qubits} qubits\n"
        "Participant-designed connectivity"
    )
    ax.set_aspect("equal")
    ax.axis("off")
    fig.tight_layout()
    fig.savefig(output_path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def compile_one_circuit(logical, config, circuit_name):
    """Compile one logical circuit and return its metrics for one processor."""
    name = config["name"]
    num_physical_qubits = int(config["num_qubits"])
    edges = config["coupling_map_directed"]
    target_basis = config["basis_gates"]

    if logical.num_qubits > num_physical_qubits:
        raise ValueError(
            f"{name} has too few qubits for circuit {circuit_name}."
        )

    # Allow SWAP gates at the routing stage so they can be counted before
    # being decomposed into the target basis.
    routing_basis = list(dict.fromkeys(target_basis + ["swap"]))

    # Unconstrained baseline: no processor coupling map is applied.
    baseline = transpile(
        logical,
        basis_gates=routing_basis,
        optimization_level=OPT_LEVEL,
        seed_transpiler=SEED,
    )

    baseline_ops = baseline.count_ops()
    baseline_cx = int(baseline_ops.get("cx", 0))

    # Route using the selected processor's directed coupling map.
    layout = list(range(logical.num_qubits))

    start = time.perf_counter()
    routed = transpile(
        logical,
        basis_gates=routing_basis,
        coupling_map=edges,
        initial_layout=layout,
        routing_method="sabre",
        optimization_level=OPT_LEVEL,
        seed_transpiler=SEED,
    )
    routing_seconds = time.perf_counter() - start

    routed_ops = routed.count_ops()
    inserted_swaps = int(routed_ops.get("swap", 0))

    # Translate the routed circuit into the processor target basis.
    # The routing step above already selected physical locations.
    start = time.perf_counter()
    final_circuit = transpile(
        routed,
        basis_gates=target_basis,
        optimization_level=OPT_LEVEL,
        seed_transpiler=SEED,
    )
    translation_seconds = time.perf_counter() - start

    final_ops = final_circuit.count_ops()
    final_cx = int(final_ops.get("cx", 0))
    remaining_swaps = int(final_ops.get("swap", 0))

    row = {
        "processor": name,
        "circuit": circuit_name,
        "benchmark_type": (
            "C1_H2_ansatz"
            if circuit_name == "h2_four_qubit_ansatz"
            else "supplementary_routing_probe"
        ),
        "physical_qubits_available": num_physical_qubits,
        "logical_qubits": logical.num_qubits,
        "compiled_circuit_width": final_circuit.num_qubits,
        "active_physical_qubits": active_physical_qubits(final_circuit),
        "logical_depth": logical.depth(),
        "routed_depth_before_swap_decomposition": routed.depth(),
        "transpiled_depth": final_circuit.depth(),
        "final_transpiled_depth": final_circuit.depth(),
        "logical_gate_count": logical.size(),
        "transpiled_gate_count": final_circuit.size(),
        "final_transpiled_gate_count": final_circuit.size(),
        "baseline_cx_count": baseline_cx,
        "transpiled_cx_count": final_cx,
        "final_transpiled_cx_count": final_cx,
        "cx_overhead_vs_unconstrained": final_cx - baseline_cx,
        "routing_swaps_before_decomposition": inserted_swaps,
        "remaining_explicit_swap_count": remaining_swaps,
        "compile_time_seconds": round(
            routing_seconds + translation_seconds, 6
        ),
        "routing_time_seconds": round(routing_seconds, 6),
        "translation_time_seconds": round(translation_seconds, 6),
        "optimization_level": OPT_LEVEL,
        "routing_method": "sabre",
        "initial_layout": str(layout),
        "transpiler_seed": SEED,
        "noise_executed": False,
        "benchmark_status": "connectivity_constrained_compilation_only",
        "architecture_status": "participant_designed",
    }

    print("\n" + "=" * 60)
    print(f"{name} - {circuit_name}")
    print("=" * 60)

    for key, value in row.items():
        print(f"{key}: {value}")

    return row


def save_results(rows):
    """Save current benchmark data to CSV, JSON, and a comparison plot."""
    if not rows:
        raise RuntimeError("No benchmark rows were generated.")

    csv_path = TABLES / "processor_comparison.csv"
    json_path = TABLES / "processor_comparison.json"
    figure_path = FIGURES / "processor_comparison.png"

    # Save a full CSV table.
    fieldnames = list(rows[0].keys())

    with csv_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    # Save JSON metadata and the full results.
    comparison_data = {
        "benchmark_settings": {
            "optimization_level": OPT_LEVEL,
            "routing_method": "sabre",
            "transpiler_seed": SEED,
            "noise_executed": False,
            "architecture_status": "participant_designed",
        },
        "results": rows,
    }

    with json_path.open("w", encoding="utf-8") as file:
        json.dump(comparison_data, file, indent=2)

    # Build a comparison plot from the newly measured rows.
    circuit_names = [
        "h2_four_qubit_ansatz",
        "four_qubit_routing_probe",
    ]
    circuit_labels = ["H2 ansatz", "Routing probe"]
    processor_names = ["Processor A", "Processor B"]

    row_lookup = {
        (row["processor"], row["circuit"]): row
        for row in rows
    }

    required_keys = [
        (processor, circuit)
        for processor in processor_names
        for circuit in circuit_names
    ]

    missing = [key for key in required_keys if key not in row_lookup]
    if missing:
        raise RuntimeError(f"Missing expected benchmark rows: {missing}")

    metrics = [
        ("final_transpiled_depth", "Final transpiled depth"),
        ("final_transpiled_cx_count", "Final transpiled CX count"),
    ]

    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    x_positions = np.arange(len(circuit_names))
    bar_width = 0.35

    for ax, (metric_key, metric_title) in zip(axes, metrics):
        for index, processor_name in enumerate(processor_names):
            values = [
                row_lookup[(processor_name, circuit_name)][metric_key]
                for circuit_name in circuit_names
            ]

            offset = (index - 0.5) * bar_width
            ax.bar(
                x_positions + offset,
                values,
                bar_width,
                label=processor_name,
            )

        ax.set_title(metric_title)
        ax.set_xticks(x_positions)
        ax.set_xticklabels(circuit_labels)
        ax.set_ylabel("Count")
        ax.legend()
        ax.grid(axis="y", alpha=0.25)

    fig.suptitle("Processor A vs Processor B: Compilation Comparison")
    fig.tight_layout()
    fig.savefig(figure_path, dpi=180, bbox_inches="tight")
    plt.close(fig)

    print(f"\nSaved CSV: {csv_path}")
    print(f"Saved JSON: {json_path}")
    print(f"Saved comparison figure: {figure_path}")
    print("Benchmark results saved successfully.")


def main():
    """Load current H2 parameters, benchmark both processors, and save results."""
    energy_path = TABLES / "h2_energy.json"

    if not energy_path.exists():
        raise FileNotFoundError(
            f"Missing H2 results at {energy_path}. "
            "Run python src/h2_solver.py first."
        )

    energy_data = load_json(energy_path)
    parameters = energy_data.get("vqe_optimal_parameters")

    if not parameters:
        raise ValueError(
            f"No vqe_optimal_parameters found in {energy_path}."
        )

    h2_circuit = build_ansatz(parameters)

    circuits = {
        "h2_four_qubit_ansatz": h2_circuit,
        "four_qubit_routing_probe": build_routing_probe(),
    }

    rows = []

    for processor_file in ("processor_A.json", "processor_B.json"):
        config_path = PROCESSOR_DIR / processor_file

        if not config_path.exists():
            raise FileNotFoundError(
                f"Missing processor configuration: {config_path}"
            )

        config = load_json(config_path)

        graph_path = (
            FIGURES / f"{processor_file.replace('.json', '_graph')}.png"
        )
        draw_processor_graph(config, graph_path)
        print(f"Connectivity graph saved: {graph_path}")

        for circuit_name, logical in circuits.items():
            row = compile_one_circuit(
                logical=logical,
                config=config,
                circuit_name=circuit_name,
            )
            rows.append(row)

    save_results(rows)


if __name__ == "__main__":
    main()
