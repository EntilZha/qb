from extract_features import kGRANULARITIES, kFEATURES, kFOLDS
from extract_features import kMIN_APPEARANCES
from util.reweight_labels import kNEG_WEIGHTS
from extractors.classifier import kCLASSIFIER_FIELDS

kVWOPT = {"mohit": "--early_terminate 100 -k -b 24 --loss_function logistic"}
kQBDB = "data/questions.db"
kFINAL_MOD = "mohit"

# Path of wikifier input for expo files
kWIKIFIER_EXPO_IN = "data/wikifier/data/expo_input"
kWIKIFIER_EXPO_OUT = "data/wikifier/data/expo_output"

assert kFINAL_MOD in kVWOPT, "Final model (%s) not in the set of VW models" % \
    kFINAL_MOD


def base_feat(feat):
    if feat.startswith("ir"):
        return "ir"
    else:
        return feat

if __name__ == "__main__":
    o = open("Makefile", 'w')
    feature_prereq = set()

    o.write("""    # -------------------------------------------------------
    # This Makefile is automatically generated.  If you want to change the
    # system, e.g. to add additional features, then edit the file
    # generate_makefile.py instead.
    # -------------------------------------------------------
""")

    # Glove data
    o.write("data/deep/glove.840B.300d.txt.gz:\n")
    o.write("\tmkdir -p data/deep\n")
    o.write("\tcurl http://www-nlp.stanford.edu/data/glove.840B.300d.txt.gz")
    o.write(" > $@\n\n")

    # Deep guesser
    feature_prereq.add("data/deep/params")
    o.write("data/deep/params: data/deep/glove.840B.300d.txt.gz\n")
    o.write("\tpython guesser/util/format_dan.py ")
    o.write("--database=%s --threshold=%i\n" % (kQBDB, kMIN_APPEARANCES))
    o.write("\tpython guesser/util/load_embeddings.py\n")
    o.write("\tpython guesser/dan.py\n\n")

    # Classifiers
    for cc in kCLASSIFIER_FIELDS:
        o.write("data/classifier/%s.pkl: " % cc)
        o.write("util/classifier.py extractors/classifier.py\n")
        o.write("\tmkdir -p data/classifier\n")
        o.write("\tpython util/classifier.py --attribute=%s\n\n"
                % cc)

    # Generate per sentence text files
    o.write("data/wikifier/data/input: util/wikification.py\n")
    o.write("\trm -rf $@\n")
    o.write("\tmkdir -p $@\n")
    o.write("\tpython util/wikification.py\n\n")

    # Generate wiki links data
    o.write("data/wikifier/data/output: data/wikifier/data/input\n")
    o.write("\trm -rf $@\n")
    o.write("\tmkdir -p $@\n")
    o.write("\t(cd data/wikifier && java -Xmx10G -jar ")
    o.write("../../lib/wikifier-3.0-jar-with-dependencies.jar ")
    o.write("-annotateData data/input data/output ")
    o.write("false ../../lib/STAND_ALONE_GUROBI.xml)\n\n")

    # Rule for generating IR lookup
    for cc in [kMIN_APPEARANCES]:
        o.write("data/ir/whoosh_wiki_%i: util/build_whoosh.py\n" % cc)
        o.write("\trm -rf $@\n")
        o.write("\tmkdir -p $@\n")
        o.write("\tmkdir -p data/wikipedia\n")
        o.write("\tpython util/build_whoosh.py ")
        o.write("--min_answers=%i " % cc)
        o.write("--whoosh_index=$@ --use_wiki\n\n")

        o.write("data/ir/whoosh_qb_%i: util/build_whoosh.py\n" % cc)
        o.write("\trm -rf $@\n")
        o.write("\tmkdir -p $@\n")
        o.write("\tpython util/build_whoosh.py --whoosh_index=$@ ")
        o.write("--min_answers=%i " % cc)
        o.write("--use_qb\n\n")

    # Rule for generating the guess list
    o.write("data/guesses.db: extract_features.py data/deep/params")
    o.write("\n")
    o.write("\tpython extract_features.py --guesses " +
            "--ans_limit=%i " % kMIN_APPEARANCES +
            "--guess_db=data/temp_guesses.db\n\n")
    o.write("\tcp data/temp_guesses.db $@\n\n")

    # Rule for generating LM model
    o.write("data/lm.pkl: extractors/lm.py\n")
    o.write("\tpython extractors/lm.py --min_answers=%i\n\n" % kMIN_APPEARANCES)

    # Generate rules for generating the features
    for gg in kGRANULARITIES:
        o.write("\n")
        o.write(" ".join("features/%s/%s.label.feat" % (x, gg)
                         for x in kFOLDS))
        o.write(": extract_features.py\n")

        for cc in kFOLDS:
            o.write("\tmkdir -p features/%s\n" % cc)
        o.write("\tpython extract_features.py --label --granularity=%s\n\n"
                % gg)

        for ff in kFEATURES:
            o.write("\n")
            o.write(' '.join("features/%s/%s.%s.feat" % (x, gg, ff)
                             for x in kFOLDS) + ': ')
            o.write("extract_features.py " +
                    "extractors/%s.py" % base_feat(ff))
            if ff == "ir":
                o.write(" ")
                o.write(" ".join("data/ir/whoosh_wiki_%i data/ir/whoosh_qb_%i"
                                 % (x, x) for x in [kMIN_APPEARANCES]))
                for cc in [kMIN_APPEARANCES]:
                    feature_prereq.add("data/ir/whoosh_wiki_%i" % cc)
                    feature_prereq.add("data/ir/whoosh_qb_%i" % cc)

            if ff == "wikilinks":
                o.write(" ")
                o.write("data/wikifier/data/output")
                feature_prereq.add("data/wikifier/data/output")

            if ff == "lm":
                o.write(" ")
                o.write("data/lm.pkl")
                feature_prereq.add("data/lm.pkl")

            if ff == "classifier":
                for cc in kCLASSIFIER_FIELDS:
                    fname = "data/classifier/%s.pkl" % cc
                    o.write(" %s" % fname)
                    feature_prereq.add(fname)

            # All features depend on guesses being generated
            o.write(" data/guesses.db\n")

            for cc in kFOLDS:
                o.write("\tmkdir -p features/%s\n" % cc)
            o.write("\tpython extract_features.py --feature=%s " % ff +
                    "--granularity=%s\n\n" % gg)

    # Create label files with the desired weights
    for gg in kGRANULARITIES:
        for ff in kFOLDS:
            o.write(" ".join("features/%s/%s.label." % (ff, gg) + str(int(x))
                             for x in kNEG_WEIGHTS))
            o.write(": features/%s/%s.label.feat\n" % (ff, gg))
            o.write("\tpython util/reweight_labels.py $<")
            o.write("\n\n")

    # Generate the training data
    # (TODO): Perhaps create versions with different subsets of the features?
    # (TODO): Perhaps compress the training files after pasting them together?
    for gg in kGRANULARITIES:
        for ff in kFOLDS:
            for ww in kNEG_WEIGHTS:
                feature_filenames = ' '.join("features/%s/%s.%s.feat" %
                                             (ff, gg, x) for x in kFEATURES)
                o.write("features/%s/%s.%i.vw_input: " % (ff, gg, int(ww)))
                o.write(feature_filenames)
                o.write(" features/%s/%s.label.%i\n\t" % (ff, gg, int(ww)))
                o.write("paste features/%s/%s.label.%i " % (ff, gg, int(ww)) +
                        " ".join("features/%s/%s.%s.feat"  % (ff, gg, x)
                                 for x in kFEATURES))
                if ff == "train":
                        temp_file = "vw_temp.%s.%s.%i" % (gg, ff, ww)
                        o.write(" | gzip > %s\n" % temp_file)
                        o.write("\tpython scripts/shuffle.py %s $@\n" % temp_file)
                        o.write("\trm %s" % temp_file)
                else:
                        o.write(" | gzip > $@")
                o.write("\n\n")

    # Generate the VW model files and predictions
    for gg in kGRANULARITIES:
        for ll in kVWOPT:
            for ww in kNEG_WEIGHTS:
                # Model files
                model_file = "models/%s.%s.%i.vw" % (gg, ll, int(ww))
                o.write("%s: " % model_file)
                assert "dev" in kFOLDS, "Need training data to create models"
                o.write("features/%s/%s.%i.vw_input\n" %
                        ("dev", gg, int(ww)))
                o.write("\tmkdir -p models\n")
                o.write("\tvw --compressed -d $< %s -f $@ " % kVWOPT[ll])
                if "--ngram" in kVWOPT[ll] or " -q " in kVWOPT[ll] or \
                        " --quadratic" in kVWOPT[ll]:
                    o.write("\n")
                else:
                    o.write("--invert_hash models/%s.%s.%i.read\n" %
                            (gg, ll, int(ww)))
                    o.write("\tpython ")
                    o.write("util/sort_features.py models/%s.%s.%i.read" %
                            (gg, ll, int(ww)))
                    o.write(" models/%s.%s.%i.sorted\n" % (gg, ll, int(ww)))
                    o.write("\trm models/%s.%s.%i.read\n" % (gg, ll, int(ww)))

                # Generate predictions
                for ff in kFOLDS:
                    o.write("\nresults/%s/%s.%i.%s.pred: " %
                            (ff, gg, int(ww), ll))
                    input_file = "features/%s/%s.%i.vw_input" % \
                        (ff, gg, int(ww))

                    o.write("%s %s\n" % (input_file, model_file))
                    o.write("\tmkdir -p results/%s\n" % ff)
                    o.write("\tvw --compressed -t -d %s -i %s " %
                            (input_file, model_file) +
                            kVWOPT[ll] + " -p $@\n")
                    o.write("\n")

                    o.write("results/%s/%s.%i.%s.buzz: " %
                            (ff, gg, int(ww), ll))
                    o.write(" results/%s/%s.%i.%s.pred " %
                            (ff, gg, int(ww), ll))
                    o.write("reporting/evaluate_predictions.py\n")
                    o.write("\tpython reporting/evaluate_predictions.py ")
                    o.write("--buzzes=$@ ")
                    o.write("--qbdb=%s " % kQBDB)
                    o.write("--question_out=results/%s/questions.csv " % ff)
                    o.write("--meta=features/%s/%s.meta " % (ff, gg))
                    o.write("--perf=results/%s/%s.%i.%s.perf " %
                            (ff, gg, int(ww), ll))
                    o.write("--neg_weight=%f " % ww)
                    o.write("--vw_config=%s " % ll)
                    o.write("--pred=$<")
                    o.write("\n\n")

    # generate restrictions
    for gg in kGRANULARITIES:
        for ff in kFOLDS:
            if ff == "train" or ff == "dev":
                continue
            for ww in kNEG_WEIGHTS:
                o.write("features/restrict/%s/train.%s.%i.vw_input:"
                        % (ff, gg, ww))
                o.write(" features/dev/%s.%i.vw_input" % (gg, ww))
                o.write(" features/%s/%s.%i.vw_input" % (ff, gg, ww))
                o.write("\n")
                o.write("\tmkdir -p features/restrict/%s\n" % ff)
                o.write("\tpython util/restrict_answer.py ")
                o.write("--answer_set_source features/%s/%s.%i.vw_input "
                        % (ff, gg, ww))
                o.write("--unfiltered_vw features/dev/%s.%i.vw_input "
                        % (gg, ww))
                o.write("--meta_in features/dev/%s.meta " % gg)
                o.write("--meta_out features/restrict/%s/train.%s.meta "
                        % (ff, gg))
                o.write("--vw_out $@")
                o.write("\n\n")

                o.write("features/restrict/%s/%s.%i.vw_input:"
                        % (ff, gg, ww))
                o.write(" features/%s/%s.%i.vw_input" % (ff, gg, ww))
                o.write("\n")
                o.write("\tmkdir -p features/restrict/%s\n" % ff)
                o.write("\tpython util/restrict_answer.py ")
                o.write("--answer_set_source features/%s/%s.%i.vw_input "
                        % (ff, gg, ww))
                o.write("--unfiltered_vw features/%s/%s.%i.vw_input "
                        % (ff, gg, ww))
                o.write("--meta_in features/%s/%s.meta " % (ff, gg))
                o.write("--meta_out features/restrict/%s/%s.meta "
                        % (ff, gg))
                o.write("--vw_out $@")
                o.write("\n\n")

    # generate models
    for gg in kGRANULARITIES:
        for ll in kVWOPT:
            for ff in kFOLDS:
                if ff == "train" or ff == "dev":
                    continue
                for ww in kNEG_WEIGHTS:
                    o.write("models/restrict/%s.%s.%s.%i.vw: " %
                            (gg, ll, ff, ww))
                    o.write("features/restrict/%s/dev.%s.%i.vw_input\n" %
                            (ff, gg, ww))
                    o.write("\tmkdir -p models/restrict\n")
                    o.write("\tvw --compressed -d $< %s -f $@ " % kVWOPT[ll])
                    if "--ngram" in kVWOPT[ll] or " -q " in kVWOPT[ll] or \
                        " --quadratic" in kVWOPT[ll]:
                        None
                    else:
                        o.write("--invert_hash models/restrict/%s.%s.%i.read\n" %
                            (ll, ff, int(ww)))
                        o.write("\tpython ")
                        o.write("util/sort_features.py models/restrict/%s.%s.%i.read" %
                                (ll, ff, int(ww)))
                        o.write(" models/restrict/%s.%s.%i.sorted\n" %
                                (ll, ff, int(ww)))
                        o.write("\trm models/restrict/%s.%s.%i.read\n" %
                                (ll, ff, int(ww)))
                    o.write("\n\n")

    # predictions from restricted models
    for gg in kGRANULARITIES:
        for ll in kVWOPT:
            for ff in kFOLDS:
                if ff == "train":
                    continue
                for ww in kNEG_WEIGHTS:
                    # Switch input file to do the filtering
                    # input_file = "features/%s/%s.%i.vw_input" % (ff, gg, ww)
                    input_file = "features/restrict/%s/%s.%i.vw_input" % \
                        (ff, gg, ww)
                    model_file = "models/restrict/%s.%s.%s.%i.vw" % \
                        (gg, ll, ff, ww)
                    o.write("results/restrict/%s/%s.%i.%s.pred: " %
                            (ff, gg, ww, ll))
                    o.write("%s " % model_file)
                    o.write("%s\n" % input_file)
                    o.write("\tmkdir -p results/restrict/%s\n" % ff)
                    o.write("\tvw --compressed -t -d %s -i %s " %
                            (input_file, model_file) +
                            kVWOPT[ll] + " -p $@\n\n")

                    # performance from restricted models
                    o.write("results/restrict/%s/%s.%i.%s.buzz: " %
                            (ff, gg, int(ww), ll))
                    o.write(" results/restrict/%s/%s.%i.%s.pred " %
                            (ff, gg, ww, ll))
                    o.write("reporting/evaluate_predictions.py\n")
                    o.write("\tmkdir -p results/%s\n" % ff)
                    o.write("\tpython reporting/evaluate_predictions.py ")
                    o.write("--buzzes=$@ ")
                    o.write("--qbdb=%s " % kQBDB)
                    o.write("--question_out=results/restrict/%s/questions.csv " % ff)
                    # o.write("--meta=features/%s/%s.meta " % (ff, gg))
                    o.write("--meta=features/restrict/%s/%s.meta " % (ff, gg))
                    o.write("--perf=results/restrict/%s/%s.%i.%s.perf " %
                            (ff, gg, ww, ll))
                    o.write("--neg_weight=%f " % ww)
                    o.write("--vw_config=%s " % ll)
                    o.write("--pred=$<")
                    o.write("\n\n")

    # Target for all predictions
    o.write("# Train all of the models")
    for gg in kGRANULARITIES:
        all_vw_models = []
        for ll in kVWOPT:
            for ww in kNEG_WEIGHTS:
                all_vw_models.append("models/%s.%s.%i.vw" % (gg, ll, int(ww)))
        o.write("\n\nall_%s_models: " % gg + " ".join(all_vw_models) + "\n\n")

    # Target for all buzzes
    o.write("# Buzz predictions for all models")
    for gg in kGRANULARITIES:
        all_buzzes = []
        for ll in kVWOPT:
            for ww in kNEG_WEIGHTS:
                for ff in kFOLDS:
                    all_buzzes.append("results/%s/%s.%i.%s.buzz" %
                                      (ff, gg, int(ww), ll))
        o.write("\n\nall_%s_buzz: " % gg + " ".join(all_buzzes) + "\n\n")

    # Target for all performances
    o.write("# Get performance summaries\n")
    for ff in kFOLDS:
        for gg in kGRANULARITIES:
            o.write("results/%s.%s.csv: " % (ff, gg))
            all_perfs = []
            for ll in kVWOPT:
                for ww in kNEG_WEIGHTS:
                    all_perfs.append("results/%s/%s.%i.%s" %
                                     (ff, gg, int(ww), ll))
            o.write(" ".join("%s.buzz" % x for x in all_perfs))
            o.write(" reporting/summarize.py\n\t")
            o.write("python reporting/summarize.py --output $@ -p ")
            o.write(" ".join("%s.perf" % x for x in all_perfs))
            o.write("\n\n")

    for ff in kFOLDS:
        for gg in kGRANULARITIES:
            o.write("results/%s.%s.pdf: results/%s.%s.csv\n\t" %
                    (ff, gg, ff, gg))
            o.write("Rscript reporting/running_score.R $< $@\n\n")

    # Expo wikifier
    o.write("%s: data/expo.csv util/wikification.py\n" %
            (kWIKIFIER_EXPO_IN))
    o.write("\trm -rf $@\n")
    o.write("\tmkdir -p $@\n")
    o.write("\tpython util/wikification.py --output_directory=$@")
    o.write(" --database='' --min_pages=-1 --expo=data/expo.csv\n\n")

    o.write("%s: %s\n" % (kWIKIFIER_EXPO_OUT, kWIKIFIER_EXPO_IN))
    o.write("\trm -rf $@\n")
    o.write("\tmkdir -p $@\n")
    o.write("\t(cd data/wikifier && java -Xmx10G -jar ")
    o.write("../../lib/wikifier-3.0-jar-with-dependencies.jar ")
    o.write("-annotateData %s %s " %
            (kWIKIFIER_EXPO_IN.replace("data/wikifier/", ""),
             kWIKIFIER_EXPO_OUT.replace("data/wikifier/", "")))
    o.write("false ../../lib/STAND_ALONE_GUROBI.xml)\n")
    o.write("\tcp $@/* data/wikifier/data/output\n\n")


    # Expo features
    o.write("features/expo/word.label.feat: ")
    o.write("extract_expo_features.py ")
    o.write(" ".join(feature_prereq))
    o.write(" %s" % kWIKIFIER_EXPO_OUT)
    o.write("\n\tmkdir -p features/expo")
    o.write("\n\tmkdir -p results/expo")
    o.write("\n\trm data/expo_guess.db")
    o.write("\n\tpython extract_expo_features.py")
    o.write("\n\n")

    # Expo labels
    o.write(" ".join("features/expo/word.label.%i" % x for x in kNEG_WEIGHTS))
    o.write(": features/expo/word.label.feat\n")
    o.write("\tpython util/reweight_labels.py $<\n\n")

    # produce restrictions
    for ww in kNEG_WEIGHTS:
        o.write("features/expo/expo.%i.vw_input: features/expo/word.label.%i"
                % (ww, ww))
        o.write("\n\t")
        o.write("paste features/expo/word.label.%i" % ww)
        for ff in kFEATURES:
            o.write(" features/expo/word.%s.feat" % ff)
        o.write("| gzip > $@\n\n")

        train_file = "features/dev/sentence.%i.vw_input" % ww
        o.write("features/expo/train.%i.vw_input: features/expo.%i.vw_input"
                % (ww, ww))
        o.write("%s\n" % train_file)
        o.write("\tpython util/restrict_answer.py ")
        o.write("--answer_set_source $<")
        o.write("--unfiltered_vw ")
        o.write(train_file)
        o.write(" --vw_out $@")
        o.write("\n\n")

        # train models
        for mm in kVWOPT:
            o.write("models/restrict.%s.%i.vw: features/expo/expo.%i.vw_input\n" %
                    (mm, ww, ww))
            o.write("\tvw --compressed -d $< %s -f $@ " % kVWOPT[mm])
            if "--ngram" in kVWOPT[mm] or " -q " in kVWOPT[mm] or \
                    " --quadratic" in kVWOPT[mm]:
                o.write("\n")
            else:
                o.write("--invert_hash models/expo/restrict/%s.%i.read\n" %
                        (mm, int(ww)))
                o.write("\tpython ")
                o.write("util/sort_features.py models/restrict/%s.%i.read" %
                        (ll, int(ww)))
                o.write(" models/restrict/%s.%i.sorted\n" % (mm, int(ww)))
                o.write("\trm models/restrict/%s.%i.read\n" % (mm, int(ww)))
                o.write("\n")

    # produce predictions and buzzes
    for ww in kNEG_WEIGHTS:
        # predictions
        input_file = "features/expo/expo.%i.vw_input" % ww
        model_file = "models/sentence.%s.%i.vw" % (kFINAL_MOD, ww)
        o.write("results/expo/expo.%i.pred: %s" % (ww, input_file))
        # Having trouble bypassing this dependency, so deleting
        # o.write(" %s" % model_file)
        o.write("\n")
        o.write("\tvw --compressed -t -d %s -i %s " %
                (input_file, model_file) + kVWOPT[kFINAL_MOD] + " -p $@\n\n")

        # Buzzes
        o.write("results/expo/expo.%i.buzz: results/expo/expo.%i.pred\n" %
                (ww, ww))
        o.write("\tmkdir -p results/expo\n")
        o.write("\tpython reporting/evaluate_predictions.py ")
        o.write("--buzzes=$@ ")
        o.write("--qbdb=%s " % kQBDB)
        o.write("--question_out='' ")
        o.write("--meta=features/expo/word.meta ")
        o.write("--perf=results/expo/word.%i.%s.perf " %
                            (int(ww), kFINAL_MOD))
        o.write("--neg_weight=%f " % ww)
        o.write("--vw_config=%s " % ll)
        o.write("--expo=data/expo.csv ")
        o.write("--finals=results/expo/expo.%i.final " % ww)
        o.write("--pred=$<")
        o.write("\n\n")

    # target for running the demo
    for ww in kNEG_WEIGHTS:
        o.write("demo%i: results/expo/expo.%i.buzz\n" % (ww, ww))
        o.write("\tpython util/buzzer.py")
        o.write(" --questions=results/expo/questions.csv")
        o.write(" --buzzes=results/expo/expo.%i.buzz" % ww)
        o.write(" --output=results/expo/competition.csv")
        o.write(" --finals=results/expo/expo.%i.final" % ww)
        o.write(" --power=data/expo_power.csv")
        o.write('\n\n')

    o.write('\n\n')
    o.write("clean:\n")
    o.write("\trm -rf data/guesses.db features")
