# Class for generating a minhash matrix from a text corpus.
# Authors: Justin Boylan-Toomey

import numpy as np
import mmh3
import heapq
import logging
import sys
from multiprocessing import Pool


def thread_multi_hash_packed(args):
    return thread_multi_hash(*args)


def thread_multi_hash(document, hash_seeds, hash_bits):
    """ Generates a texts minhash signature using multi-hash method.

    Uses i random hashes for j permutations selecting the minimum hash value
    each time to build each texts hash signature.

    Slower but more stable than k smallest hash method.

    Args:
        document (list): List of document shingles.
        hash_seeds (list):
        hash_bits (list):

    Returns:
        list: List of text signatures generated using k smallest neighbours method.

    """
    signature = []
    for seed in np.nditer(hash_seeds):
        _min_value = None
        for shingle in document:
            if hash_bits == 64:
                hash_value = mmh3.hash64(
                    shingle, int(seed)
                )[0]
            elif hash_bits == 32:
                hash_value = mmh3.hash(
                    shingle, int(seed)
                )
            else:
                hash_value = mmh3.hash128(
                    shingle, int(seed)
                )
            if not _min_value:
                _min_value = hash_value
            elif _min_value > hash_value:
                _min_value = hash_value
        signature.append(_min_value)
    return signature


class MinHash:
    """ MinHash.

    Attributes:
        n_gram (int): Number of characters used in each shingle.
        n_gram_type (str): Type of n gram used for shingles.
        permutations (int): Number of random permutations used to generate signatures.
        hash_bits (int): Hash value size used to generate signatures.
        method (str): Method used to generate signatures.
        seed (int): Seed used to generate signatures.
        signatures (np.array): Matrix of minhash signatures, m represents each texts
            minhash signature with n representing each permutations minimum hash value.

    """

    def __init__(
            self,
            text,
            n_gram=9,
            n_gram_type='char',
            permutations=100,
            hash_bits=64,
            method='multi_hash',
            seed=None,
            n_jobs=1
    ):
        """ Generates a minhash signature matrix for texts in a corpus.

        Args:
            text (list, np.array): Iterable containing text content of each document.
            n_gram (int): Number of characters to be used in each shingle.
            n_gram_type (str): Type of n gram to use for shingles, must be char or term.
            permutations (int): Number of hash values in each document signature.
            hash_bits (int): Hash value size, must be 32, 64 or 128 bit.
            method (str): Method to be used for minhash function, must be multi_hash
                or k_smallest_values.
            seed (int): Seeds from which to generate random hash function.

        """
        logging.basicConfig(format='%(asctime)s - %(levelname)s - %(name)s -   %(message)s',
                            datefmt='%m/%d/%Y %H:%M:%S',
                            level=logging.INFO)
        logging.getLogger().addHandler(logging.StreamHandler(sys.stdout))
        self.logger = logging.getLogger(__name__)
        self.n_jobs = n_jobs
        self.n_gram = n_gram
        if n_gram_type not in ['char', 'term']:
            raise ValueError(
                'Only "char" and "term" n_gram types are supported.'
            )
        self.n_gram_type = n_gram_type
        self.permutations = permutations
        if hash_bits not in [32, 64, 128]:
            raise ValueError(
                'Only 32, 64 and 128 bit hashes are supported.'
            )
        self.hash_bits = hash_bits
        if method not in [
            'multi_hash',
            'k_smallest_values'
        ]:
            raise ValueError(
                'Only "multi_hash" and "k_smallest_value" hash methods are supported.'
            )
        self.method = method
        self.seed = None
        if seed:
            self.seed = seed
            np.random.seed(seed)
        if method == 'multi_hash':
            self._hash_seeds = np.random.randint(
                low=1, high=100_000_000, size=permutations
            )
        else:
            self._hash_seeds = np.random.randint(
                low=1, high=100_000_000
            )

        # Run methods.
        self._shingles = self._k_shingles(text, method is 'multi_hash')
        self.signatures = self._min_hash()

    def _k_shingles(self, texts, packed=False):
        """ Generates shingles for each input text.

        Breaks strings into k overlapping shingles consisting of characters or terms
        of n_gram size.

        Args:
            texts (list, np.array): list, array or Pandas series of input texts.

        Yields:
            List: Shingle list generated for each input text.

        """
        trim_overflow = (self.n_gram - 1) * -1
        if type(texts) == str:
            texts = [texts]
        for text in texts:
            if self.n_gram_type == 'char':
                shingles = [
                               text[char:char + self.n_gram]
                               for char in range(len(text))
                           ][:trim_overflow]
            else:
                terms = text.split()
                shingles = [
                               ' '.join(terms[term:term + self.n_gram])
                               for term in range(len(terms))
                           ][:trim_overflow]
            if not shingles:
                raise ValueError(
                    'Shingle "n_gram" size must not exceed minimum text length.'
                )
            if packed:
                yield shingles, self._hash_seeds, self.hash_bits
            else:
                yield shingles

    def _k_smallest_hash(self, document):
        """ Generates a texts minhash signature using k smallest neighbours method.

        Uses a single random hash to simulate a shuffle of each texts shingles.
        Then selecting i smallest minimum hash values for j permutations.

        Faster but less stable than multi hash method.

        Args:
            document (list): List of text shingles.

        Returns:
            list: List of text signatures generated using k smallest neighbours method.

        """
        signature = []
        # Uses a heap to make calculating n smallest values more efficient.
        heapq.heapify(signature)
        if len(document) <= self.permutations:
            raise ValueError(
                'N permutations must not be >= n shingles for k_smallest_values method'
            )
        for shingle in document:
            if self.hash_bits == 64:
                hashed_shingle = mmh3.hash64(
                    shingle, self._hash_seeds
                )[0]
            elif self.hash_bits == 32:
                hashed_shingle = mmh3.hash(
                    shingle, self._hash_seeds
                )
            else:
                hashed_shingle = mmh3.hash128(
                    shingle, self._hash_seeds
                )
            heapq.heappush(signature, hashed_shingle)
        return heapq.nsmallest(self.permutations, signature)

    def _min_hash(self):
        """ Calculates document signature by calling the selected hashing method.

        Returns:
             np.array: Matrix of minhash signatures, m represents each texts minhash
                signature with n representing each permutations minimum hash value.

        """
        if self.method is 'multi_hash':
            pool = Pool(self.n_jobs)
            signatures = pool.map(thread_multi_hash_packed, self._shingles)
            return np.array(signatures)
        else:
            signatures = []
            for document in self._shingles:
                signature = self._k_smallest_hash(document)
                signatures.append(signature)
            return np.array(signatures)
