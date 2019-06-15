from setuptools import setup

setup(name='jaccardupy',
      version='0.1',
      description='Near Duplicate Text Detection Library.',
      url='https://github.com/justinnbt/LSH',
      license='MIT',
      author='Justin Boylan-Toomey',
      author_email='justin.boylan-toomey@outlook.com',
      packages=['jaccardupy'],
      install_requires=['Cython', 'numpy'])
