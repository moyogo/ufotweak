from setuptools import setup, find_packages

setup(
    name="ufotweak",
    version="0.0.1",
    description="UFO font source command line tweaker",
    url="https://github.com/moyogo/ufotweaker",
    license="MIT license",
    author="Denis Moyogo Jacquerye",
    author_email="moyogo@gmail.com",
    platforms=["any"],
    packages=find_packages("lib"),
    package_dir={"": "lib"},
    install_requires=[
        "fonttools[ufo]",
        "ufolib2",
    ],
    entry_points={
        "console_scripts": [
            "ufotweak = ufotweak.__main__:main",
        ],
    },
    keywords="font, typeface, ufo",
    include_package_data=True,
    classifiers=[
        'Development Status :: 4 - Beta',
        'Natural Language :: English',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ],
)
