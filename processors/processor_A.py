"""Processor A configuration for Q-Molecule Phase 1.

The architecture and ports are participant-designed assumptions,
not official organizer-provided hardware specifications.
"""

import json
from pathlib import Path

NUM_QUBITS = 5

# Participant-designed undirected coupling graph.
COUPLING_EDGES = [
    (0, 1),
    (1, 2),
    (2, 3),
    (3, 0),
    (2, 4),
]

BASIS_GATES = ["rz", "sx", "x", "cx"]

# Illustrative parameters, not official hardware values.
NOISE_MODEL = {
    "enabled": True,
    "model": "depolarizing_with_symmetric_readout",
    "parameter_status": "illustrative_assumption_not_official",
    "single_qubit_depolarizing_probability": 0.001,
    "two_qubit_depolarizing_probability": 0.01,
    "readout_error_probability": 0.02,
}

# Participant-selected ports, not official assignments.
PORTS = [0, 4]


def make_directed_map(edges):
    """Represent every undirected edge in both directions."""
    directed = []

    for a, b in edges:
        directed.append([a, b])
        directed.append([b, a])

    return directed


def validate_config(num_qubits, edges, ports):
    """Validate edges, ports, and graph connectivity."""
    if num_qubits < 1:
        raise ValueError("num_qubits must be positive.")

    seen = set()

    for a, b in edges:
        if not (0 <= a < num_qubits and 0 <= b < num_qubits):
            raise ValueError(f"Invalid qubit index in edge {(a, b)}.")

        if a == b:
            raise ValueError("Self-coupling edges are not allowed.")

        edge = tuple(sorted((a, b)))
        if edge in seen:
            raise ValueError(f"Duplicate undirected edge: {edge}")

        seen.add(edge)

    if len(ports) != 2 or ports[0] == ports[1]:
        raise ValueError("Exactly two distinct ports are required.")

    if any(
        not isinstance(p, int) or p < 0 or p >= num_qubits
        for p in ports
    ):
        raise ValueError("Port indices must refer to valid qubits.")

    adjacency = {i: set() for i in range(num_qubits)}

    for a, b in edges:
        adjacency[a].add(b)
        adjacency[b].add(a)

    visited = set()
    stack = [0]

    while stack:
        node = stack.pop()

        if node in visited:
            continue

        visited.add(node)
        stack.extend(adjacency[node] - visited)

    if len(visited) != num_qubits:
        raise ValueError("The processor coupling graph is disconnected.")


def build_config():
    """Build a JSON-serializable Processor A definition."""
    validate_config(NUM_QUBITS, COUPLING_EDGES, PORTS)

    return {
        "name": "Processor A",
        "num_qubits": NUM_QUBITS,
        "ports": PORTS,
        "ports_status": "participant_selected_not_official",
        "architecture": "participant_designed_nonlinear_baseline",
        "architecture_status": "custom_design_not_an_official_edge_list",

        # Schema-compatible undirected edge list.
        "coupling_map": [
            list(edge) for edge in COUPLING_EDGES
        ],

        # Existing directed map used by the compilation benchmark.
        "coupling_edges_undirected": [
            list(edge) for edge in COUPLING_EDGES
        ],
        "coupling_map_directed": make_directed_map(COUPLING_EDGES),

        "basis_gates": BASIS_GATES,

        # Keep both keys for compatibility with the project.
        "noise": NOISE_MODEL,
        "noise_model": NOISE_MODEL,

        "benchmark_policy": {
            "compare_connectivity_without_noise": True,
            "apply_noise_only_in_separate_experiment": True,
        },
    }


def main():
    config = build_config()
    output = Path(__file__).resolve().parent / "processor_A.json"

    output.write_text(
        json.dumps(config, indent=2),
        encoding="utf-8",
    )

    print(f"Created: {output}")
    print(f"Qubits: {NUM_QUBITS}")
    print(f"Undirected couplings: {len(COUPLING_EDGES)}")
    print(f"Ports: {PORTS} (participant-selected)")
    print("Architecture validation: PASS")
    print("Schema fields: PASS")
    print("Noise parameters are illustrative, not official.")


if __name__ == "__main__":
    main()