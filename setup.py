from setuptools import setup, find_packages

version = '0.0.1'

setup(name='aws.cc',
      version=version,
      description="AWS Hacks.",
      classifiers=[
          "Programming Language :: Python",
      ],
      keywords='fabric',
      author='ITDEV.Online.Team@medibankhealth.com.au',
      author_email='ITDEV.Online.Team@medibankhealth.com.au',
      url='https://confluence.fitness2live.net.au/display/F2LOPS/monitoring',
      license='',
      packages=find_packages('.'),
      include_package_data=True,
      zip_safe=False,
      install_requires=[
          'setuptools',
          # -*- Extra requirements: -*-
      ],
      )
