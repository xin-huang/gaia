# GNU General Public License v3.0
# Copyright 2024 Xin Huang
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, please see
#
#    https://www.gnu.org/licenses/gpl-3.0.en.html


import demes, msprime, os, tskit
import pyranges as pr
from gaia.utils.simulators import DataSimulator


class MsprimeSimulator(DataSimulator):
    """
    MsprimeSimulator extends DataSimulator to simulate genetic data using the msprime package.

    This subclass specifies simulation parameters for msprime and inherits additional
    simulation configuration from the DataSimulator class.

    """
    def __init__(self, demo_model_file: str,  nref: int, ntgt: int, 
                 ref_id: str, tgt_id: str, src_id: str, ploidy: int,
                 seq_len: int, mut_rate: float, rec_rate: float,
                 output_prefix: str, output_dir: str, is_phased: bool):
        """
        Initializes a new instance of MsprimeSimulator with specific parameters for msprime simulations.

        Parameters
        ----------
        demo_model_file : str
            Path to the demographic model file, which defines the demographic history to simulate.
        nref : int
            Number of samples in the reference population.
        ntgt : int
            Number of samples in the target population.
        ref_id : str
            Identifier for the reference population in the demographic model.
        tgt_id : str
            Identifier for the target population in the demographic model.
        src_id : str
            Identifier for the source population in the demographic model.
        ploidy : int
            Ploidy of the samples; typically 2 for diploid organisms.
        seq_len : int
            Length of the sequence to simulate, in base pairs.
        mut_rate : float
            Mutation rate per base pair per generation.
        rec_rate : float
            Recombination rate per base pair per generation.
        output_prefix : str
            Prefix for the output files generated by the simulation.
        output_dir : str
            Directory where the output files will be stored.
        is_phased : bool
            Indicates whether the true tracts should be considered as unphased.

        Attributes
        ----------
        test_tgt_id : str
            Used to store the identifier for the target population that is subject to 
            introgression analysis, initialized based on the `tgt_id` parameter. Its purpose is 
            to identify the specific subset of individuals within the target population being 
            analyzed for introgression. This distinction becomes crucial when the study focuses 
            on a selected subset from the larger group identified by `tgt_id`. If the analysis 
            shifts to a different subset or the definition of the target population changes, 
            `test_tgt_id` should be updated to accurately reflect the group under investigation.

        """
        super().__init__(demo_model_file=demo_model_file, nref=nref, ntgt=ntgt,
                         ref_id=ref_id, tgt_id=tgt_id, src_id=src_id, ploidy=ploidy,
                         seq_len=seq_len, mut_rate=mut_rate, rec_rate=rec_rate,
                         output_prefix=output_prefix, output_dir=output_dir)
        self.test_tgt_id = self.tgt_id
        self.is_phased = is_phased


    def run(self, rep: int = None, seed: int = None) -> list[dict[str, str]]:
        """
        Executes the simulation with optional runtime arguments.

        Outputs multiple files including simulation results and metadata.

        Parameters
        ----------
        rep : int or None
            Used to specify the replicate number for the simulation. This attribute is not set
            in the constructor but should be assigned before running simulations that require
            tracking or distinguishing between multiple replicates.
        seed : int or None
            Seed for the random number generator to ensure reproducibility of the simulations.
            Similar to `rep`, this is not directly set in the constructor but should be specified
            to ensure that simulations can be reproduced exactly.

        Returns
        -------
        list[dict[str, str]]
            A list of a dictionary containing file paths for the simulated data.

        """
        output_dir = self.output_dir if rep is None else os.path.join(self.output_dir, str(rep))
        output_prefix = self.output_prefix if rep is None else f'{self.output_prefix}.{rep}'

        os.makedirs(output_dir, exist_ok=True)
        ts_file = os.path.join(output_dir, f'{output_prefix}.ts')
        vcf_file = os.path.join(output_dir, f'{output_prefix}.vcf')
        bed_file = os.path.join(output_dir, f'{output_prefix}.true.tracts.bed')
        ref_ind_file = os.path.join(output_dir, f'{output_prefix}.ref.ind.list')
        tgt_ind_file = os.path.join(output_dir, f'{output_prefix}.tgt.ind.list')
        seed_file = os.path.join(output_dir, f'{output_prefix}.seedmsprime')

        file_paths = {
            'ts_file': ts_file, 
            'vcf_file': vcf_file, 
            'bed_file': bed_file,
            'ref_ind_file': ref_ind_file, 
            'tgt_ind_file': tgt_ind_file, 
            'seed_file': seed_file,
        }

        self._create_ref_tgt_file(self.nref, self.ntgt, ref_ind_file, tgt_ind_file)


        demo_graph = demes.load(self.demo_model_file)
        demography = msprime.Demography.from_demes(demo_graph)
        samples = [
            msprime.SampleSet(self.nref, ploidy=self.ploidy, population=self.ref_id),
            msprime.SampleSet(self.ntgt, ploidy=self.ploidy, population=self.test_tgt_id),
        ]

        ts = msprime.sim_ancestry(
            recombination_rate=self.rec_rate,
            sequence_length=self.seq_len,
            samples=samples,
            demography=demography,
            record_migrations=True,
            random_seed=seed,
        )
        ts = msprime.sim_mutations(ts, rate=self.mut_rate, random_seed=seed, model=msprime.BinaryMutationModel())

        ts.dump(ts_file)
        with open(vcf_file, 'w') as o: ts.write_vcf(o)
        if seed is not None:
            with open(seed_file, 'w') as o: 
                o.write(f'{seed}\n')

        true_tracts = self._get_true_tracts(ts, self.tgt_id, self.src_id, self.ploidy, self.is_phased)
        true_tracts = pr.from_string(true_tracts).merge(by='Sample')

        if true_tracts.empty: open(bed_file, 'w').close()
        else: true_tracts.to_csv(bed_file, sep="\t", header=False)

        return [file_paths]


    def _create_ref_tgt_file(self, nref: int, ntgt: int, ref_ind_file: str, 
                             tgt_ind_file: str, identifier: str ="tsk_") -> None:
        """
        Creates files listing reference and target individual identifiers.

        Parameters
        ----------
        nref : int
            Number of reference individuals.
        ntgt : int
            Number of target individuals.
        ref_ind_file : str
            Path to the output file for reference individuals.
        tgt_ind_file : str
            Path to the output file for target individuals.
        identifier : str, optional
            Prefix for individual identifiers (default is "tsk_").

        """
        with open(ref_ind_file, 'w') as f:
            for i in range(nref):
                f.write(identifier + str(i) + "\n")

        with open(tgt_ind_file, 'w') as f:
            for i in range(nref, nref + ntgt):
                f.write(identifier + str(i) + "\n")


    def _get_true_tracts(self, ts: tskit.TreeSequence, tgt_id: str, src_id: str, 
                         ploidy: int, is_phased: bool) -> str:
        """
        Generates a string representing the true migration tracts between specified source and target populations within a given tskit.TreeSequence.

        Parameters
        ----------
        ts : tskit.TreeSequence
            The tree sequence object containing the simulation data.
        tgt_id : str
            The identifier for the target population.
        src_id : str
            The identifier for the source population.
        ploidy : int
            The ploidy of the genome.
        is_phased : bool
            Indicates whether the data is phased.

        Returns
        -------
        tracts : str
            A string containing the tracts information in BED format.
            The columns include chromosome (fixed to '1' in this implementation), start, end, and sample identifier.

        Raises
        ------
        ValueError
            If `src_id` or `tgt_id` is not found.

        """
        tracts = "Chromosome\tStart\tEnd\tSample\n"
        
        try:
            src_id = [p.id for p in ts.populations() if p.metadata['name']==src_id][0]
        except IndexError:
            raise ValueError(f'Population {src_id} is not found.')

        try:
            tgt_id = [p.id for p in ts.populations() if p.metadata['name']==tgt_id][0]
        except IndexError:
            raise ValueError(f'Population {tgt_id} is not found.')

        tgt_samples = ts.samples(tgt_id)
        ts, migtable = self._simplify_ts(ts=ts, tgt_id=tgt_id, src_id=src_id)

        #for m in ts.migrations():
        #    if (m.dest==src_id) and (m.source==tgt_id):
        for m in migtable:
                # For simulations with a long sequence, large sample size, and/or deep generation time
                # This function may become slow
                # Use new arguments from https://github.com/tskit-dev/tskit/pull/2762
                # for t in ts.trees(left=m.left, right=m.right):
            for t in ts.trees():
                if m.left >= t.interval.right: continue
                if m.right <= t.interval.left: break # [l, r)
                #for n in ts.samples(tgt_id):
                for n in tgt_samples:
                    if t.is_descendant(n, m.node):
                        left = m.left if m.left > t.interval.left else t.interval.left
                        right = m.right if m.right < t.interval.right else t.interval.right
                        if is_phased: sample_id = f'tsk_{ts.node(n).individual}_{int(n%ploidy+1)}'
                        else: sample_id = f'tsk_{ts.node(n).individual}'
                        tracts += f'1\t{int(left)}\t{int(right)}\t{sample_id}\n'

        return tracts
    

    def _simplify_ts(self, ts: tskit.TreeSequence, tgt_id: str, src_id: str) -> tskit.TreeSequence:
        """
        """
        from copy import deepcopy

        #now we create reduced tree sequence objects
        ts_dump_mig = ts.dump_tables()
        migtable = ts_dump_mig.migrations
        migtable2 = deepcopy(migtable)
        migtable2.clear()

        #we search for all rows involving source and target
        for mrow in migtable:
            if (mrow.dest==src_id) and (mrow.source==tgt_id):
                migtable2.append(mrow)

        #the new tree sequence stores only the relevant migrations (involving source and target)
        ts_dump_mig.migrations.replace_with(migtable2)
        ts_dump_sequence_mig = ts_dump_mig.tree_sequence()

        #in the other tree sequence, we delete all migration events
        ts_dump = ts.dump_tables()
        ts_dump.migrations.clear()
        ts_dump_sequence = ts_dump.tree_sequence()

        #we search for all nodes involving the relevant populations
        populations_not_to_remove = [src_id, tgt_id]
        individuals_not_to_remove = []
        for ind in ts.nodes():
            if ind.population in populations_not_to_remove:
                individuals_not_to_remove.append(ind.id)

        #the tree sequence object without migrations can be simplified
        #the simplification contains only the relevant (source-target involving) information
        ts_dump_sequence_simplified = ts_dump_sequence.simplify(
            individuals_not_to_remove, 
            filter_populations=False, 
            filter_individuals=False, 
            filter_sites=False, 
            filter_nodes=False
        )

        return ts_dump_sequence_simplified, migtable2
