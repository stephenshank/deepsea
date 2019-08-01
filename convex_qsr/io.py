import json

import numpy as np
import networkx as nx
from Bio import SeqIO
import pysam

from .error_correction import ErrorCorrection
from .mapped_reads import MappedReads
from .read_graph import SuperReadGraph
from .regression import perform_regression


def write_json(path, data):
    if path:
        with open(path, 'w') as json_file:
            json.dump(data, json_file, indent=2)


def write_fasta(path, data):
    if path:
        SeqIO.write(data, path, 'fasta')


def error_correction_io(
        input_bam, output_bam, output_json=None, output_fasta=None,
        end_correction=None, index=None
        ):
    alignment = pysam.AlignmentFile(input_bam, 'rb', index_filename=index)
    error_correction = ErrorCorrection(
        alignment, end_correction=end_correction
    )
    error_correction.write_corrected_reads(output_bam)
    pysam.index(output_bam)
    write_json(
        output_json, 
        [int(i) for i in error_correction.covarying_sites]
    )
    write_fasta(output_fasta, error_correction.consensus())


def read_graph_io(
        input_bam, input_json, input_consensus,
        output_full, output_cvs, output_describing,
        output_graph, output_candidates, index=None,
        minimum_weight=3
        ):
    with open(input_json) as json_file:
        covarying_sites = np.array(json.load(json_file), dtype=np.int)
    consensus = SeqIO.read(input_consensus, 'fasta')
    corrected_reads = MappedReads(input_bam, 'rb', index_filename=index)

    superread_graph = SuperReadGraph(corrected_reads, covarying_sites)
    superread_graph.obtain_superreads(minimum_weight)
    superread_graph.create_full()

    full_superreads = superread_graph.get_full_superreads(consensus)
    write_fasta(output_full, full_superreads)

    superread_graph.reduce()
    cvs_superreads = superread_graph.get_cvs_superreads()
    write_fasta(output_cvs, cvs_superreads)

    superread_json = nx.node_link_data(superread_graph.superread_graph)
    write_json(output_graph, superread_json)

    superread_records, describing_superreads = \
        superread_graph.get_candidate_quasispecies(consensus)
    write_json(output_describing, describing_superreads)
    write_fasta(output_candidates, superread_records)


def regression_io(
        input_superreads, input_describing_json,
        input_candidates_fasta, output_fasta
        ):
    with open(input_superreads) as superread_file:
        superreads = json.load(superread_file)['nodes']

    with open(input_describing_json) as candidates_file:
        describing = json.load(candidates_file)

    quasispecies_info = perform_regression(superreads, describing)
    candidates = list(SeqIO.parse(input_candidates_fasta, 'fasta'))
    all_quasispecies = []
    for i, quasispecies in enumerate(quasispecies_info):
        record = candidates[quasispecies['index']]
        record_info = (i + 1, quasispecies['frequency'])
        record.id = 'quasispecies-%d_frequency-%.5f' % record_info
        record.description = ''
        all_quasispecies.append(record)

    write_fasta(output_fasta, all_quasispecies)