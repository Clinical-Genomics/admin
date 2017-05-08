# When can I use the Trio-application tag
Can be used for both exomes and whole genomes (EXT and WGT) and only in cases where at least three samples are submitted in the same order
and in the same family.
All samples in the family have to be either exome or whole genome.

# Providing parental relationships (mother, father)
For a case containing more than one sample the possible parental relationship between the samples should be filled in to get a better
analysis. This is filled in for the child. If this is left out, the samples will be treated as unrelated in the analysis.

# Adding samples to an existing family
We connect the samples using family-id, it's therefor very important to assign the correct family-id to the new sample.
For example if parents are sent in to complement an analysis of the child.
First add the new samples (parents) using the same family-id of an existing sample (child).
Then add one row for the existing sample (child) where you fill in the parental relationship and mark that the sample is existing (has been
previously sequenced by Clinical Genomics).

# New analysis with updated sample information
Fill in family-id, sample-id and customer, any additional information will be used to update existing data for the sample. We will then re-run the analysis using this
new information.

# Re-analysis of the same case with a new family-id
This is not routine, it's a special case. This can be done when you are unsure about the state of illness of one of the members of
the case and want to compare the two analyses.
This creates a lot of work for us so we rather see that you are using the same family-id for a new analysis of the same family.

Process:

1. Add a family (with a new family-id) and fill in "Original family-id" from the original case
2. For samples where you want to use existing sequencing data, choose "data" as "Source"
3. You can either use the same sample name as the original sample or use a new sample name AND fill in the original sample name
   under "Original sample".
4. You need to fill in the rest of the information (sex, gene panel, state of illness) for all samples as usual - this will
   **not** be fetched from the original sample.
