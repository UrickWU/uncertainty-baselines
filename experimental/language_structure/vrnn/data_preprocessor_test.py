# coding=utf-8
# Copyright 2022 The Uncertainty Baselines Authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Tests for data_preprocessor."""

from absl.testing import absltest
from absl.testing import parameterized
import more_itertools
import tensorflow as tf
from uncertainty_baselines.datasets import datasets
import data_preprocessor  # local file import from experimental.language_structure.vrnn
import data_utils  # local file import from experimental.language_structure.vrnn
import utils  # local file import from experimental.language_structure.vrnn

INPUT_ID_NAME = data_preprocessor.INPUT_ID_NAME
INPUT_MASK_NAME = data_preprocessor.INPUT_MASK_NAME
DIAL_TURN_ID_NAME = data_preprocessor.DIAL_TURN_ID_NAME


class DataPreprocessorTest(parameterized.TestCase):

  def setUp(self):
    super().setUp()
    self.batch_size = 2

  def create_data_preprocessor(self, max_seq_length, **kwargs):
    del max_seq_length  # unused
    return data_preprocessor.DataPreprocessor(**kwargs)

  def load_dataset(self, dataset_name):
    dataset_builder = datasets.get(
        dataset_name, split='test', add_dialog_turn_id=True)
    return dataset_builder.load(batch_size=self.batch_size).prefetch(1)

  @parameterized.named_parameters(('multiwoz_synth', 'multiwoz_synth'),
                                  ('simdial', 'simdial'),
                                  ('sgd_synth', 'sgd_synth'))
  def test_output_shape(self, dataset_name):
    dataset = self.load_dataset(dataset_name)
    dialog_length = data_utils.get_dataset_max_dialog_length(dataset_name)
    seq_length = data_utils.get_dataset_max_seq_length(dataset_name)
    num_states = data_utils.get_dataset_num_latent_states(dataset_name)

    preprocessor = self.create_data_preprocessor(
        seq_length, num_states=num_states)
    dataset = dataset.map(preprocessor.create_feature_and_label)
    (input_1, input_2, label, label_mask, initial_state, initial_sample,
     domain_label) = more_itertools.first(dataset)

    for inputs in [input_1, input_2]:
      for key in [INPUT_ID_NAME, INPUT_MASK_NAME]:
        self.assertEqual([self.batch_size, dialog_length, seq_length],
                         inputs[key].shape.as_list())

    for inputs in [label, label_mask, domain_label]:
      self.assertEqual([self.batch_size, dialog_length], inputs.shape.as_list())

    for inputs in [initial_state, initial_sample]:
      self.assertEqual([self.batch_size, num_states], inputs.shape.as_list())

  @parameterized.named_parameters(('multiwoz_synth', 'multiwoz_synth'),
                                  ('simdial', 'simdial'),
                                  ('sgd_synth', 'sgd_synth'))
  def test_label_mask_by_dialog_turn_ids(self, dataset_name):
    dataset = self.load_dataset(dataset_name)
    inputs = more_itertools.first(dataset)
    dialog_turn_id_indices = [(0, 2), (1, 3), (1, 5)]
    dialog_turn_ids = tf.gather_nd(inputs[DIAL_TURN_ID_NAME],
                                   dialog_turn_id_indices)
    seq_length = data_utils.get_dataset_max_seq_length(dataset_name)
    num_states = data_utils.get_dataset_num_latent_states(dataset_name)

    preprocessor = self.create_data_preprocessor(
        seq_length,
        num_states=num_states,
        labeled_dialog_turn_ids=dialog_turn_ids)
    dataset = dataset.map(preprocessor.create_feature_and_label)
    (_, _, _, label_mask, _, _, _) = more_itertools.first(dataset)

    for i, row in enumerate(label_mask.numpy()):
      for j, val in enumerate(row):
        if (i, j) in dialog_turn_id_indices:
          self.assertEqual(val, 1)
        else:
          self.assertEqual(val, 0)


class BertDataPreprocessorTest(DataPreprocessorTest):

  def create_data_preprocessor(self, max_seq_length, **kwargs):
    preprocess_tfhub_url = 'https://tfhub.dev/tensorflow/bert_en_uncased_preprocess/3'
    bert_preprocess_model = utils.BertPreprocessor(preprocess_tfhub_url,
                                                   max_seq_length)
    return data_preprocessor.BertDataPreprocessor(bert_preprocess_model,
                                                  **kwargs)


if __name__ == '__main__':
  absltest.main()