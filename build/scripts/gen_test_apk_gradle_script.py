import argparse
import os
import tarfile
import xml.etree.ElementTree as etree

FLAT_DIRS_REPO_TEMPLATE='repositories {{ flatDir {{ dirs {dirs} }} }}'
MAVEN_REPO_TEMPLATE='maven {{ url "{repo}" }}\n'

TEST_APK_TEMPLATE = """\
ext.jniLibsDirs = [
    {jni_libs_dirs}
]
ext.resDirs = [
    {res_dirs}
]
ext.javaDirs = [
    {java_dirs}
]
ext.bundles = [
    {bundles}
]

{flat_dirs_repo}

buildscript {{
//    repositories {{
//        jcenter()
//    }}
    dependencies {{
        classpath 'com.android.tools.build:gradle:2.3.0+'
    }}
}}

apply plugin: 'com.android.application'

repositories {{
//     maven {{
//         url "http://maven.google.com/"
//     }}
//    maven {{
//        url "http://artifactory.yandex.net/artifactory/public/"
//    }}
//    flatDir {{
//        dirs System.env.PKG_ROOT + '/bundle'
//    }}
{maven_repos}
}}

dependencies {{
    for (bundle in bundles) {{
        compile("$bundle")
    }}
}}

android {{
    compileSdkVersion 28
    buildToolsVersion "28.0.2"


    defaultConfig {{
        minSdkVersion 15
        targetSdkVersion 28
        applicationId "{app_id}"
    }}

    sourceSets {{
        main {{
            manifest.srcFile 'Manifest.xml'
            jniLibs.srcDirs = jniLibsDirs
            res.srcDirs = resDirs
            java.srcDirs = javaDirs
        }}
    }}

    applicationVariants.all {{ variant ->
        variant.outputs.each {{ output ->
            output.outputFile = file("$projectDir/output/{app_id}.apk")
        }}
    }}

    dependencies {{
        compile 'com.android.support:support-v4:28.0.0'
        compile 'com.google.android.gms:play-services-location:11.8.0'

        compile 'com.android.support:support-compat:27.0.0'
        compile 'com.google.android.gms:play-services-gcm:11.8.0'
        compile 'com.evernote:android-job:1.2.6'
    }}
}}
"""


def create_native_properties(output_dir, library_name):
    native_properties_file = os.path.join(output_dir, 'native_library_name.xml')
    resources = etree.Element('resources')
    name = etree.SubElement(resources, 'item', dict(name='native_library_name', type='string'))
    name.text = library_name
    etree.ElementTree(resources).write(native_properties_file, xml_declaration=True, encoding='utf-8')



def gen_build_script(args):
    def wrap(items):
        return ',\n    '.join('"{}"'.format(x) for x in items)

    bundles = []
    bundles_dirs = set()
    for bundle in args.bundles:
        dir_name, base_name = os.path.split(bundle)
        assert(len(dir_name) > 0 and len(base_name) > 0)
        name, ext = os.path.splitext(base_name)
        assert(len(name) > 0 and ext == '.aar')
        bundles_dirs.add(dir_name)
        bundles.append('com.yandex:{}@aar'.format(name))

    if len(bundles_dirs) > 0:
        flat_dirs_repo = FLAT_DIRS_REPO_TEMPLATE.format(dirs=wrap(bundles_dirs))
    else:
        flat_dirs_repo = ''

    maven_repos = ''.join(MAVEN_REPO_TEMPLATE.format(repo=repo) for repo in args.maven_repos)

    return TEST_APK_TEMPLATE.format(
        app_id=args.app_id,
        jni_libs_dirs=wrap(args.jni_libs_dirs),
        res_dirs=wrap(args.res_dirs),
        java_dirs=wrap(args.java_dirs),
        maven_repos=maven_repos,
        bundles=wrap(bundles),
        flat_dirs_repo=flat_dirs_repo
    )


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--aars', nargs='*', default=[])
    parser.add_argument('--app-id', required=True)
    parser.add_argument('--assets-dirs', nargs='*', default=[])
    parser.add_argument('--bundles', nargs='*', default=[])
    parser.add_argument('--bundle-name', nargs='?', default=None)
    parser.add_argument('--java-dirs', nargs='*', default=[])
    parser.add_argument('--jni-libs-dirs', nargs='*', default=[])
    parser.add_argument('--library-name', required=True)
    parser.add_argument('--manifest', required=True)
    parser.add_argument('--maven-repos', nargs='*', default=[])
    parser.add_argument('--output-dir', required=True)
    parser.add_argument('--peers', nargs='*', default=[])
    parser.add_argument('--res-dirs', nargs='*', default=[])
    args = parser.parse_args()

    for index, jsrc in enumerate(filter(lambda x: x.endswith('.jsrc'), args.peers)):
        jsrc_dir = os.path.join(args.output_dir, 'jsrc_{}'.format(str(index)))
        os.makedirs(jsrc_dir)
        with tarfile.open(jsrc, 'r') as tar:
            tar.extractall(path=jsrc_dir)
            args.java_dirs.append(jsrc_dir)

    args.build_gradle = os.path.join(args.output_dir, 'build.gradle')
    args.settings_gradle = os.path.join(args.output_dir, 'settings.gradle')

    content = gen_build_script(args)
    with open(args.build_gradle, 'w') as f:
        f.write(content)

    if args.bundle_name:
        with open(args.settings_gradle, 'w') as f:
            f.write('rootProject.name = "{}"'.format(args.bundle_name))

    values_dir = os.path.join(args.output_dir, 'res', 'values')
    os.makedirs(values_dir)
    create_native_properties(values_dir, args.library_name)