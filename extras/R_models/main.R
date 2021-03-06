library(ggplot2)

this.dir <- dirname(parent.frame(2)$ofile)
setwd(this.dir)
source("load_db.R")
source("model.R")

db_path = '/Users/ajaver/OneDrive - Imperial College London/compare_strains_DB/control_experiments_short_movies_new.db'
#db_path = '/Users/ajaver/OneDrive - Imperial College London/compare_strains_DB/control_experiments_movies_2h.db'
experiments = read.experiments(db_path)

control.strain = 'N2'
feat.table = 'medians_split'

#features.names = read.features.names(db_path)
features.names = c('midbody_speed_pos', 'midbody_bend_mean_pos', 'length') 
features.data = read.feats(db_path, features.names, feat.table, control.strain)
strains.stats = get.models(features.data, control.strain)

features.data = features.data[, N_Worms_f:=factor(N_Worms)]#useful for plotting
for (feat.name in features.names[1:3]) {
  #p <- ggplot( aes(x = experiment_id, y = log2(abs(midbody_speed+1)), fill=strain), data=feat_table) + geom_boxplot()
  valid = is.finite(features.data[[feat.name]])
  valid.data = features.data[valid,]
  
  #y_str = paste0("log2(abs(", feat_name, "+1))")
  p <- ggplot(valid.data, aes_string(x = "Strain", y = feat.name, colour = "N_Worms_f"))
  p <- p + geom_boxplot() + facet_grid(exp_name ~ .)
  print(p)
}
