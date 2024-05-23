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


import os
from typing import Any
from gaia.utils.simulators import DataSimulator
from gaia.utils.simulators import MsprimeSimulator
from gaia.utils.generators import GenomicDataGenerator
from gaia.utils.labelers import BinaryWindowLabeler
from gaia.utils.preprocessors import FeatureVectorsPreprocessor


class LRTrainingDataSimulator(DataSimulator):
    """
    A simulator class that integrates simulation, labeling, and feature vector generation
    to prepare data for logistic regression training.

    This class automates the process of simulating genomic data, labeling the simulated data
    based on introgression, generating genomic features, and merging labels with features to
    create a comprehensive dataset ready for machine learning model training.

    """
    def __init__(self, demo_model_file: str, nref: int, ntgt: int, 
                 ref_id: str, tgt_id: str, src_id: str, ploidy: int,
                 seq_len: int, mut_rate: float, rec_rate: float,
                 output_prefix: str, output_dir: str, is_phased: bool,
                 intro_prop: float, non_intro_prop: float, feature_config: str):
        """
        Initializes a new instance of LRTrainingDataSimulator with specific parameters.

        Parameters
        ----------
        demo_model_file : str
            Path to the demographic model file defining the simulation parameters.
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
        seq_len : int
            Length of the simulated sequence, in base pairs.
        mut_rate : float
            Mutation rate per base pair per generation.
        rec_rate : float
            Recombination rate per base pair per generation.
        output_prefix : str
            Prefix for the output files generated by the simulation.
        output_dir : str
            Directory where the output files will be stored.
        intro_prop : float
            Proportion threshold for labeling a window as introgressed.
        non_intro_prop : float
            Proportion threshold for labeling a window as not introgressed.

        Attributes
        ----------
        simulator : MsprimeSimulator
            An instance of MsprimeSimulator for simulating genomic data based on demographic models.
        labeler : BinaryWindowLabeler
            An instance of BinaryWindowLabeler for labeling simulated genomic data based on introgression events.
        win_len : int
            Length of the sliding window used for feature generation and labeling, in base pairs.
        ploidy : int
            Ploidy of the samples; typically 2 for diploid organisms. Affects labeling and feature generation.
        is_phased : bool
            Indicates whether the simulated genomic data is phased. Affects labeling and feature generation.
        feature_config : str
            Path to the YAML configuration file specifying which features to compute for the dataset.

        """
        self.simulator = MsprimeSimulator(
            demo_model_file=demo_model_file,
            nref=nref,
            ntgt=ntgt,
            ref_id=ref_id,
            tgt_id=tgt_id,
            src_id=src_id,
            ploidy=ploidy,
            seq_len=seq_len,
            mut_rate=mut_rate,
            rec_rate=rec_rate,
            output_prefix=output_prefix,
            output_dir=output_dir,
            is_phased=is_phased,
        )

        self.labeler = BinaryWindowLabeler(
            ploidy=ploidy,
            is_phased=is_phased,
            win_len=seq_len,
            intro_prop=intro_prop,
            non_intro_prop=non_intro_prop,
        )

        self.win_len = seq_len
        self.ploidy = ploidy
        self.is_phased = is_phased
        self.feature_config = feature_config


    def run(self, rep: int = None, seed: int = None) -> list[dict[str, Any]]:
        """
        Executes the simulation, labeling, and feature vector generation workflow for a given replicate.

        This method runs the entire pipeline, from data simulation to feature vector generation, and merges
        the generated labels with the feature vectors based on sample identifiers. It is designed to facilitate
        the preparation of datasets for machine learning model training, specifically logistic regression.

        Parameters
        ----------
        rep : int, optional
            The replicate number for distinguishing multiple simulation runs. Default: None.
        seed : int, optional
            Seed for the random number generator to ensure reproducibility of the simulation. Default: None.

        Returns
        -------
        list[dic[str, Any]]
            A list of dictionaries, each representing a merged record containing both feature vectors and labels
            for a single sample in the dataset. Each dictionary includes keys for genomic coordinates (`'Chromosome'`,
            `'Start'`, `'End'`), sample identifier (`'Sample'`), statistical features, and the introgression label.

        """
        file_paths = self.simulator.run(rep=rep, seed=seed)[0]

        labels = self.labeler.run(
            tgt_ind_file=file_paths['tgt_ind_file'],
            true_tract_file=file_paths['bed_file'],
            rep=rep,
        )

        genomic_data_generator = GenomicDataGenerator(
            vcf_file=file_paths['vcf_file'],
            ref_ind_file=file_paths['ref_ind_file'],
            tgt_ind_file=file_paths['tgt_ind_file'],
            chr_name='1',
            win_len=self.win_len,
            win_step=self.win_len,
            ploidy=self.ploidy,
            is_phased=self.is_phased,
        )

        preprocessor = FeatureVectorsPreprocessor(
            ref_ind_file=file_paths['ref_ind_file'],
            tgt_ind_file=file_paths['tgt_ind_file'],
            feature_config=self.feature_config,
        )

        features = preprocessor.run(
            **list(genomic_data_generator.get())[0]        
        )

        lookup = {item['Sample']: item for item in labels}
        merged_list = [{**item, **lookup[item['Sample']]} for item in features]

        return merged_list
